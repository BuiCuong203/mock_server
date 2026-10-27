// pubsub_mock: GCP Pub/Sub giả lập cho input gcp_pubsub của CyM-Log-Shipper.
//
// Dùng pstest (fake server chính chủ trong cloud.google.com/go/pubsub) làm gRPC Pub/Sub, thêm:
//   - tự tạo topic / subscription theo streams/gcp_pubsub.json
//   - bộ sinh message theo tốc độ (rate message/giây) từ template
//   - HTTP admin: GET /status, POST /publish
//
// Shipper (thư viện Go của Google) tự chuyển sang emulator khi có biến môi trường
// PUBSUB_EMULATOR_HOST=<host>:<grpc-port>; credentials_base64 vẫn bắt buộc nhưng không được kiểm tra.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"net/http"
	"os"
	"os/signal"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"cloud.google.com/go/pubsub/apiv1/pubsubpb"
	"cloud.google.com/go/pubsub/pstest"
	"github.com/google/uuid"
)

type generatorConf struct {
	Rate      float64           `json:"rate"`
	Backlog   int               `json:"backlog"`
	Templates []json.RawMessage `json:"templates"`
	Attrs     map[string]string `json:"attributes"`
}

type topicConf struct {
	Name          string         `json:"name"`
	Subscriptions []string       `json:"subscriptions"`
	Generator     *generatorConf `json:"generator"`
}

type projectConf struct {
	ProjectID string      `json:"project_id"`
	Topics    []topicConf `json:"topics"`
}

type fileConf struct {
	Projects []projectConf `json:"projects"`
}

type topicState struct {
	fullName  string
	templates []string
	attrs     map[string]string
	seq       atomic.Int64
	published atomic.Int64
	paused    atomic.Bool
	rate      float64
	subs      []string
}

var (
	srv    *pstest.Server
	topics = map[string]*topicState{}
	mu     sync.Mutex
	acked  atomic.Int64
)

var (
	reRandInt = regexp.MustCompile(`\{\{RANDOM_INT:(\d+):(\d+)\}\}`)
	reChoice  = regexp.MustCompile(`\{\{CHOICE:([^{}]*)\}\}`)
)

// render thay placeholder trong template (chuỗi JSON hoặc text)
func render(tpl string, seq int64, t time.Time) string {
	s := strings.ReplaceAll(tpl, `"{{SEQ}}"`, strconv.FormatInt(seq, 10))
	s = strings.ReplaceAll(s, "{{SEQ}}", strconv.FormatInt(seq, 10))
	s = strings.ReplaceAll(s, "{{EVENT_TIME_ISO}}", t.UTC().Format("2006-01-02T15:04:05.000Z"))
	s = strings.ReplaceAll(s, "{{EVENT_TIME_MS}}", strconv.FormatInt(t.UnixMilli(), 10))
	s = strings.ReplaceAll(s, "{{EVENT_TIME}}", strconv.FormatInt(t.Unix(), 10))
	s = strings.ReplaceAll(s, "{{NOW_ISO}}", time.Now().UTC().Format(time.RFC3339))
	s = strings.ReplaceAll(s, "{{NOW_MS}}", strconv.FormatInt(time.Now().UnixMilli(), 10))
	for strings.Contains(s, "{{UUID}}") {
		s = strings.Replace(s, "{{UUID}}", uuid.NewString(), 1)
	}
	s = reRandInt.ReplaceAllStringFunc(s, func(m string) string {
		g := reRandInt.FindStringSubmatch(m)
		lo, _ := strconv.Atoi(g[1])
		hi, _ := strconv.Atoi(g[2])
		if hi < lo {
			hi = lo
		}
		return strconv.Itoa(lo + rand.Intn(hi-lo+1))
	})
	s = reChoice.ReplaceAllStringFunc(s, func(m string) string {
		opts := strings.Split(reChoice.FindStringSubmatch(m)[1], "|")
		return opts[rand.Intn(len(opts))]
	})
	return s
}

// template là chuỗi JSON thì gửi nguyên chuỗi đó, là object JSON thì gửi dạng JSON nén
func templateText(raw json.RawMessage) string {
	var s string
	if json.Unmarshal(raw, &s) == nil {
		return s
	}
	var v interface{}
	if json.Unmarshal(raw, &v) == nil {
		b, _ := json.Marshal(v)
		return string(b)
	}
	return string(raw)
}

func publishOne(ts *topicState, data string, attrs map[string]string) {
	if attrs == nil {
		attrs = ts.attrs
	}
	srv.Publish(ts.fullName, []byte(data), attrs)
	ts.published.Add(1)
}

func publishGenerated(ts *topicState) {
	seq := ts.seq.Add(1) - 1
	tpl := ts.templates[int(seq)%len(ts.templates)]
	publishOne(ts, render(tpl, seq, time.Now()), nil)
}

func runGenerator(ctx context.Context, ts *topicState) {
	if ts.rate <= 0 || len(ts.templates) == 0 {
		return
	}
	interval := time.Duration(float64(time.Second) / ts.rate)
	next := time.Now()
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(time.Until(next)):
		}
		for !next.After(time.Now()) {
			if !ts.paused.Load() {
				publishGenerated(ts)
			}
			next = next.Add(interval)
		}
	}
}

// pstest giữ mọi message đã publish trong bộ nhớ: dọn khi tất cả đã được ack
func janitor(ctx context.Context) {
	tick := time.NewTicker(30 * time.Second)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-tick.C:
		}
		msgs := srv.Messages()
		all := len(msgs) > 0
		n := 0
		for _, m := range msgs {
			if m.Acks > 0 {
				n++
			} else {
				all = false
			}
		}
		if all || len(msgs) > 200000 {
			acked.Add(int64(n))
			srv.ClearMessages()
		}
	}
}

func setup(cfg fileConf) {
	ctx := context.Background()
	for _, p := range cfg.Projects {
		for _, t := range p.Topics {
			full := fmt.Sprintf("projects/%s/topics/%s", p.ProjectID, t.Name)
			if _, err := srv.GServer.CreateTopic(ctx, &pubsubpb.Topic{Name: full}); err != nil {
				log.Printf("CreateTopic %s: %v", full, err)
			}
			ts := &topicState{fullName: full}
			for _, s := range t.Subscriptions {
				subName := fmt.Sprintf("projects/%s/subscriptions/%s", p.ProjectID, s)
				_, err := srv.GServer.CreateSubscription(ctx, &pubsubpb.Subscription{
					Name: subName, Topic: full, AckDeadlineSeconds: 30,
				})
				if err != nil {
					log.Printf("CreateSubscription %s: %v", subName, err)
				}
				ts.subs = append(ts.subs, subName)
			}
			if g := t.Generator; g != nil {
				ts.rate = g.Rate
				ts.attrs = g.Attrs
				for _, raw := range g.Templates {
					ts.templates = append(ts.templates, templateText(raw))
				}
			}
			mu.Lock()
			topics[full] = ts
			mu.Unlock()
			// backlog: message có sẵn trước khi shipper kết nối
			if t.Generator != nil && len(ts.templates) > 0 {
				for i := 0; i < t.Generator.Backlog; i++ {
					publishGenerated(ts)
				}
			}
			log.Printf("topic %s: %d subscription, generator %.2f msg/s, backlog %d", full, len(ts.subs), ts.rate, ts.published.Load())
		}
	}
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func handleStatus(w http.ResponseWriter, _ *http.Request) {
	mu.Lock()
	defer mu.Unlock()
	out := []map[string]interface{}{}
	for name, ts := range topics {
		out = append(out, map[string]interface{}{
			"topic": name, "subscriptions": ts.subs, "rate": ts.rate, "paused": ts.paused.Load(),
			"published": ts.published.Load(),
		})
	}
	pending := 0
	for _, m := range srv.Messages() {
		if m.Acks == 0 {
			pending++
		}
	}
	writeJSON(w, 200, map[string]interface{}{"status": "online", "topics": out,
		"acked_total": acked.Load() + int64(len(srv.Messages())-pending), "unacked": pending})
}

// POST /publish {"project": "...", "topic": "...", "messages": [obj|"text"], "count": n, "attributes": {...}}
// Không có messages -> publish n message sinh từ template của topic.
func handlePublish(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, 405, map[string]string{"error": "POST only"})
		return
	}
	var req struct {
		Project  string            `json:"project"`
		Topic    string            `json:"topic"`
		Messages []json.RawMessage `json:"messages"`
		Count    int               `json:"count"`
		Attrs    map[string]string `json:"attributes"`
		Pause    *bool             `json:"pause"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, map[string]string{"error": err.Error()})
		return
	}
	full := req.Topic
	if !strings.HasPrefix(full, "projects/") {
		full = fmt.Sprintf("projects/%s/topics/%s", req.Project, req.Topic)
	}
	mu.Lock()
	ts := topics[full]
	mu.Unlock()
	if ts == nil {
		writeJSON(w, 404, map[string]string{"error": "topic không tồn tại: " + full})
		return
	}
	if req.Pause != nil {
		ts.paused.Store(*req.Pause)
	}
	n := 0
	for _, raw := range req.Messages {
		publishOne(ts, render(templateText(raw), ts.seq.Add(1)-1, time.Now()), req.Attrs)
		n++
	}
	if len(req.Messages) == 0 {
		for i := 0; i < req.Count; i++ {
			publishGenerated(ts)
			n++
		}
	}
	writeJSON(w, 200, map[string]interface{}{"success": true, "published": n, "topic": full, "paused": ts.paused.Load()})
}

func main() {
	grpcPort := flag.Int("grpc-port", 8085, "cổng gRPC Pub/Sub (PUBSUB_EMULATOR_HOST)")
	grpcHost := flag.String("grpc-host", "0.0.0.0", "địa chỉ nghe gRPC (0.0.0.0 = mọi địa chỉ)")
	httpAddr := flag.String("http-addr", ":8086", "địa chỉ HTTP admin (/status, /publish)")
	confPath := flag.String("config", "streams/gcp_pubsub.json", "file cấu hình topic / subscription / generator")
	flag.Parse()

	var cfg fileConf
	b, err := os.ReadFile(*confPath)
	if err != nil {
		log.Fatalf("đọc %s: %v", *confPath, err)
	}
	if err := json.Unmarshal(b, &cfg); err != nil {
		log.Fatalf("parse %s: %v", *confPath, err)
	}

	// NewServerWithPort chỉ nghe localhost -> trong Docker shipper ở máy khác không tới được: nghe mọi địa chỉ
	srv = pstest.NewServerWithAddress(fmt.Sprintf("%s:%d", *grpcHost, *grpcPort))
	defer srv.Close()
	setup(cfg)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	mu.Lock()
	for _, ts := range topics {
		go runGenerator(ctx, ts)
	}
	mu.Unlock()
	go janitor(ctx)

	mux := http.NewServeMux()
	mux.HandleFunc("/status", handleStatus)
	mux.HandleFunc("/publish", handlePublish)
	go func() {
		log.Printf("HTTP admin: %s (/status, /publish)", *httpAddr)
		if err := http.ListenAndServe(*httpAddr, mux); err != nil {
			log.Fatalf("http admin: %v", err)
		}
	}()
	log.Printf("Pub/Sub gRPC sẵn sàng tại %s  ->  shipper: PUBSUB_EMULATOR_HOST=<ip-mock>:%d", srv.Addr, *grpcPort)

	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)
	<-sig
	log.Printf("dừng pubsub_mock")
}
