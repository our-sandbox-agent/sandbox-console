# 實作計劃：詳細版（2026-09）

> 語言已定案（2026-09-21）：Runner 與 CLI 用 Go，控制平面 TypeScript。第 1 步直接以 Go 實作 Runner，第 3 步第 0 項只做接線，不再有 Node → Go 改寫。見 [Runner 語言 ADR](adr/runner-language.md)。

> 這是給工程師看的完整版。創辦人先看短版 [plan.md](plan.md)。

> 首版範圍與兩個待決策取捨見 [受邀試用版](plan.md#受邀試用版收斂後的範圍2026-09-21)。完整 Alpha 與提前受限試用是不同放行路線，目前未選定；工程票依賴如何調整見本文件最後一節。

> 這份文件把「從雛形到能收費的產品」拆成 8 步，給創辦人看：每一步做完會看到什麼、要多久、先做哪一步、哪些事要你決定。技術結論來自各步驟已審過的計劃，這裡只做整理、排序與統一用語。每步的估時都是 **1 位工程師** 的週數；兩位工程師時，第 1、2 步可以並行（其他可並行的組合見第 1 節第 9 點）。用法：先看第 1、2 節決定順序與里程碑，第 3 節是每一步的細節（每步只有「目標」「做完會看到」「預估」「風險」「先不做」是給你看的，其餘可以跳過），第 5 節是需要你拍板的事。

## 0. 原則

1. **每一步做完都要有看得到的成果**：不是「後端好了」，而是創辦人能在雛形或終端機親手操作到；步驟太大就拆成兩段（一律叫 A 段／B 段），A 段先交付。
2. **先 gVisor 後 Firecracker**：一般 VPS（租用的虛擬主機）沒有 KVM（硬體虛擬化）就走 gVisor（Google 的使用者空間核心，用攔截系統呼叫來隔離）；Firecracker（AWS 的微型虛擬機）要裸機，留到最後，而且先用數字決定值不值得。
3. **能用開源就不自己寫，但不引進超出團隊能力的平台**：Docker（容器）、tmux（讓終端畫面留在伺服器端）、ttyd／xterm.js（把終端搬進網頁）、Caddy（自動配 HTTPS 的網頁伺服器）、WireGuard（兩台主機間的加密隧道）、nftables（Linux 防火牆）、Stripe（收款）都直接用；Nomad、Consul、K8s（多機排程平台）、Vault（祕密管理系統）一律不碰。
4. **先單租戶再多租戶，先單機再多機**：一台 VPS 跑控制平面、一台 VDS 跑沙盒；多主機排程、跨主機恢復都往後放。
5. **先做 Claude 再做另外兩個**：Claude Code 是主打入口，驗收都以它為準；Codex 盡力支援，Harness 等創辦人定義是哪個工具再說。

## 1. 總覽

| 順序 | 步驟 | 做完你會看到什麼 | 預估 | 依賴 |
|---|---|---|---|---|
| 1 | runner-mvp：真沙盒 | 開發模式下按「Try in console」，Terminal 分頁變成真的 shell；打 `claude` 直接進 Claude Code；`uname -r` 印 gVisor 的 4.4.0；Suspend 後檔案還在 | 3 週 | 無 |
| 2 | control-plane：控制平面 | 用 GitHub 帳號登入 `console.<網域>`；沙盒清單、狀態、倒數、policy 都在伺服器，換一台電腦看到同一份；可發 API token 給 CLI 用 | 3.5 週 | 無 |
| 3 | cli-terminal：CLI 與終端串流 | 自己電腦 `curl … \| sh` 裝好 `sandbox`，`sandbox claude --repo URL` 10 秒內接上雲端 tmux，clone 完自動進 Claude Code；Ctrl-\ 脫離、`sandbox connect` 接回；console 按 New sandbox，VDS 上真的多一個容器；push 到 main 後 VDS 的 runner 與映像檔一分鐘內更新 | 5 週 | 1、2 |
| 4 | auto-tiering：自動降級 | 沒人敲鍵盤就自己 Active → Idle → Suspend（A 段是冷 Suspend：停容器留檔案）；Agent 在跑長任務不會被誤暫停；B 段 `sandbox connect` 從記憶體快照 1–3 秒回到同一個畫面 | 5 週 | 1、2、3 |
| 5 | workspace-files：檔案與工作區 | 每個沙盒一顆真磁碟；從 repo 真的 clone；Files 分頁列真檔、下載、500 MB 續傳上傳；Snapshot／Fork 帶著檔案與登入狀態走，快照顯示保留期；Suspend 時可選 push 分支 | 4 週 | 1、2、3、4（至少 B 段的試做） |
| 6 | secrets-network：祕密與網路 | 沙盒裡找不到真 API key 但 `claude -p` 照常回答；對外連線預設全擋、白名單放行；Network 分頁看到每筆連線 | 4 週 | 1、2、3、4（至少 B 段的試做） |
| 7 | metering-billing：計量與收費 | Usage 頁是伺服器算的真數字（四個維度）；額度上限到了自動 Suspend；Stripe 測試模式看到發票；每晚自動對帳；服務掛了或備份失敗會收到 email | 5 週 | 1、2、3、4、5 |
| 8 | firecracker-baremetal：Firecracker 與裸機 | 先用 gVisor 的數字過閘門；A 段在裸機上跑 VM 等級隔離的沙盒；B 段記憶體快照約 1 秒恢復；工作區層級的開關一關就回 gVisor | 4 週 + 3 週 | 1–7 |

累計：36.5 週（1 人）；含 15% 緩衝約 42 週。第 8 步的 B 段可以不做，或等第 8 步的閘門數字再決定。

**為什麼這樣排**

1. 第 1 步最快讓創辦人看到「真的東西」：3 週後 Terminal 分頁就是真 shell、真 Claude Code，而且 GitHub Pages 展示版完全不動。它沒有依賴，所以放最前面。
2. 第 2 步也沒有依賴，但它的成果是「登入、資料離開瀏覽器」，比較像基礎工程；兩人團隊可以跟第 1 步並行，一人團隊就排第二，因為第 3 步同時需要這兩步。第 1、2 步各自獨立做完，第 3 步一開始先把兩者接起來（控制平面加一個 `http.ts` 驅動真 runner）。
3. 第 3 步把「一行指令進沙盒」做出來，這是產品的入口，也是研究文（docs/research.md）第 3 節第 3 點「重連才是日常」。
4. 第 4 步是我們相對 E2B 的核心賣點（研究文第 3 節第 1 點「不為等 LLM 付全價」），而且第 7 步收費要靠它的事件；所以排在檔案與祕密之前。它的 A 段（自動 Idle、冷 Suspend）1 週就能 demo。
5. 第 5、6 步彼此不依賴，順序可對調，但兩步都建在第 4 步「直接驅動 runsc、自建網路」的底層上（磁碟掛法、快照時凍結、每沙盒獨立網路空間），所以至少要等第 4 步 B 段的可行性試做有結論；試做做不通，第 5、6 步各自有寫好的 Docker 退路。檔案先做是因為「從 repo 建立、Snapshot／Fork」在雛形已經有按鈕，做完最有感；祕密與網路是給外人用之前一定要有的圍欄。
6. 第 7 步要有真的狀態事件（第 4 步）與磁碟配給量（第 5 步）才有東西可算，所以在它們之後。
7. 第 8 步依賴全部，而且開頭是一個「不租機、不裝東西」的閘門：gVisor 冷恢復（見名詞表「冷開機 vs 冷恢復 vs 熱恢復」）p95 不到 5 秒、也沒有客戶要求 VM 等級隔離，就整步不做。
8. 有一個要先知道的銜接點：第 1 步用 Docker 指定 `--runtime=runsc` 跑 gVisor，最省事；但第 4 步的記憶體快照要「直接驅動 runsc、不經 Docker」，第 5、6 步的磁碟與網路也是接在 runsc 的設定檔上。所以第 1 步刻意把所有 Docker 呼叫鎖在一個檔案（`docker-adapter`），第 4 步的可行性試做（spike，3.4 做法第 4 項）就是換底層的檢查點，換底層本身另估 1 週（3.4 做法第 5 項）；換不動就停在第 4 步的 A 段。
9. **2 人時的關鍵路徑**：1‖2（3.5 週）→ 3（5 週）→ 4（5 週）→ 5‖6（4 週）→ 7（5 週）＝約 22.5 週到 M3。3.5 與 3.6 並行時，沙盒網路（netns／veth 腳本）的介面要先由一人定義，另一人才接得上；3.7 的 A 段（事件表與 usage SQL）不依賴第 6 步，也可以提早開工。

**常用名詞（第一次看到時可以回來查）**

| 名詞 | 白話 |
|---|---|
| VPS／VDS | 租用的虛擬主機。文件裡 VPS 跑控制平面（登入、資料庫、API），VDS 跑沙盒（規格較大） |
| 裸機 | 整台實體機只有我們一個租戶，有 /dev/kvm，Firecracker 需要 |
| gVisor（runsc） | Google 的沙盒執行器，在使用者空間模擬一個 Linux 核心，容器裡的程式碰不到真核心 |
| Firecracker | AWS 的微型虛擬機，E2B、Fly Sprites、Vercel 都用它；隔離最強，能存整份記憶體快照 |
| 控制平面（control plane） | 管帳號、沙盒清單、狀態、計費的伺服器；不跑沙盒本身 |
| Runner | 跑在 VDS 上、真的去建立／停止／刪除沙盒的常駐程式 |
| PTY／tmux | PTY 是假的終端機線路，讓 Claude Code 這種全螢幕程式畫得出來；tmux 讓畫面留在沙盒端，斷線再接回 |
| Suspend／Resume | 暫停與恢復。第 1 步到第 4 步 A 段是「冷 Suspend：停容器、留檔案」，第 4 步 B 段起是「暖 Suspend：存整份記憶體、回到同一個畫面」 |
| checkpoint／restore | 把沙盒整份記憶體存成檔案／讀回來繼續跑 |
| 冷開機 vs 冷恢復 vs 熱恢復 | 冷開機：沒有記憶體快照，用磁碟重新開機（第 1 步、第 4 步 A 段、第 8 步 A 段）。冷恢復：有記憶體快照，但主機快取都清掉（drop_caches）後從磁碟讀回來，是最慢的情況，閘門用它量。熱恢復：快照還在主機快取裡，最快 |
| token | 通行證字串。API token 給 CLI 用，session token 給沙盒內部用 |
| policy | 自動降級的時間門檻設定：幾分鐘沒動就 Idle、再幾分鐘 Suspend；一個工作區一份 |
| p50／p95 | 一半／95% 的次數都在這個時間內（p95 = 100 次裡最慢的 5 次以外都在這個時間內） |
| WebSocket（ws） | 瀏覽器與伺服器之間的雙向長連線，終端畫面靠它即時傳 |
| proxy／白名單 | 沙盒對外連線都先經過的中繼站；只放行名單上的網址 |
| vsock | VM 與主機之間不走網路的專用通道（第 8 步才用） |
| UFFD | Linux 讓程式按需載入記憶體的機制，恢復快照時「碰到哪頁才讀哪頁」（第 8 步才用） |
| vault | 祕密管理系統，存 API key 這類機密；我們用資料庫加密欄位代替，不裝 Vault 產品 |
| netns／veth／NAT | 每個沙盒獨立的網路空間、一對虛擬網路線、出口位址轉換 |
| overlay | 唯讀底層＋可寫上層疊起來的檔案系統，容器改動只寫在上層 |
| spike（可行性試做） | 花 2–3 天只為了回答「這條路走不走得通」的試做，不交付功能 |

## 2. 里程碑

| 里程碑 | 包含步驟 | 達成後對外可以說 | 累計週數 | 含 15% 緩衝 |
|---|---|---|---|---|
| M1：`sandbox claude` 真的能跑 | 1 runner-mvp、2 control-plane、3 cli-terminal | 一行指令，10 秒內接上雲端沙盒終端並看到 repo 正在 clone，clone 完自動進 Claude Code；關掉終端再 `sandbox connect` 畫面還在；用 GitHub 登入的網頁 console 看得到同一個畫面 | 11.5 週 | 13 週 |
| M2：關掉電腦明天回來能接續 | 4 auto-tiering、5 workspace-files | 沒人用就自動 Idle → Suspend，Agent 跑長任務不會被誤暫停；恢復後檔案、登入狀態、shell 歷史都在；若記憶體快照可行則回到同一個 tmux 畫面；從 repo 建立、Snapshot／Fork、Suspend 時 push 分支 | 20.5 週 | 23.5 週 |
| M3：能給外人用、能收費（測試模式） | 6 secrets-network、7 metering-billing | 沙盒裡沒有真 key、對外連線白名單、每筆連線有紀錄；Usage 頁是伺服器算的四維度數字、額度上限；Stripe 測試模式出帳、每晚對帳；服務掛了會收到 email | 29.5 週 | 34 週 |
| M3.5：正式收費 | 7 的做法第 8 項（含在第 7 步的 5 週內） | Stripe 切正式模式、正式費率由創辦人在 Stripe 設定、綁真卡出真發票 | 29.5 週 | 34 週 |
| M4（可選）：VM 等級隔離與秒級恢復 | 8 firecracker-baremetal | 沙盒跑在 Firecracker 微型虛擬機裡；Suspend 後約 1 秒回到同一個畫面；Fork 接著原畫面繼續跑 | 33.5 週（只做 A 段）／36.5 週（含 B 段） | 38.5 週／42 週 |

M1 之前就有可展示的中間點：第 1 步第 3 週末（開發模式下真 shell）、第 3 步第 4 天（本機 docker 就看到 Claude Code 免問答進畫面）。M2 之內：第 4 步第 1 週末（自動 Idle、冷 Suspend）、第 5 步第 2 週末（從 repo 建立 → fork → 重開機檔案還在）。M3 之內：第 6 步第 2 週末（沙盒無 key、curl 被擋）、第 7 步第 2 週末（Usage 頁真數字、額度上限）。

## 3. 各步驟計劃

> 導讀：每步的「目標」「做完會看到」「預估」「風險」「這一步先不做」是給創辦人看的；「做法」「技術選型」「驗收」是給工程師的，可以跳過。每步內部分兩段時一律叫「A 段／B 段」，做法項目一律以「做法第 N 項」互相引用。

### 3.1 runner-mvp：真沙盒（3 週）

**目標**

在一台 VPS 上用 gVisor 跑真正隔離的容器，讓 Claude Code 在裡面執行，畫面即時串到雛形的 Terminal 分頁；Suspend 停掉容器但保留 /workspace 的檔案。

**做完會看到**

1. 創辦人在自己電腦開一條 SSH 通道（`ssh -N -L 8080:127.0.0.1:8080 runner@<VPS IP>`，把遠端的 8080 埠接到本機，連線本身已加密並用金鑰驗過身分），跑 `npm run dev`，側欄按「Connect runner」貼上 token。
2. Sandboxes 頁按「Try in console」，Terminal 分頁不再是模擬文字，而是真的 shell（xterm.js，瀏覽器終端的事實標準）。打 `claude` 直接進 Claude Code，不用選主題、不用確認 key；請它「在 /workspace 建一個 hello.txt」，`ls /workspace` 看到檔案。
3. 打 `uname -r` 印的是 gVisor 的假核心版本 4.4.0，證明程式不是直接跑在主機上（工程師另用 `dmesg` 確認開機訊息是 gVisor 的）。
4. 關掉分頁再開，畫面靠 tmux 接回；切分頁、打搜尋字都不會讓終端閃爍或斷線。
5. 按 Suspend：沙盒真的停了（工程師用 `docker ps` 確認容器 Exited）；Resume 後 `cat /workspace/hello.txt` 檔案還在（畫面重來，這步先這樣）。新增 Destroy 按鈕，確認後容器與 volume 都消失。
6. 詳情頁右上「Demo session」改顯示「gVisor · live」。GitHub Pages 上的版本完全不變，沒有任何 token 或網址進打包檔。

**做法**

1. **主機準備**：租 KVM 型 VPS（Hetzner Cloud、DigitalOcean、EC2 一般機型），不要 OpenVZ／LXC 型（跟房東共用核心，Docker 跑不起來）。Ubuntu 24.04、4 vCPU / 8 GB。寫成可重跑的 `infra/vps-setup.sh`：先 `systemd-detect-virt`，是 openvz／lxc 就退出；官方 apt 裝 Docker Engine；照 gvisor.dev 裝 runsc；`sudo runsc install && sudo systemctl reload docker`。預設平台 systrap，用 seccomp（Linux 過濾系統呼叫的機制）攔截，不需要 /dev/kvm。為第 4、5 步預留的主機檢查也放在這支腳本：`stat -fc %T /sys/fs/cgroup` 必須是 `cgroup2fs`（cgroup v2）、核心 ≥ 5.6、資料碟以 `mkfs.xfs -m reflink=1` 格式化掛到 `/var/lib/sandbox`，Docker 的 data-root 也指到那顆碟；不符就退出並印原因，之後不用回頭動正在跑沙盒的主機。建專用使用者 `runner` 加進 docker 群組（第 5 步改成 root 跑、檔案程式另外降權）；SSH 只准金鑰；防火牆只開 22。驗證：`docker run --rm --runtime=runsc ubuntu:24.04 uname -r` 印 `4.4.0`。
2. **沙盒映像檔** `images/agent-base/Dockerfile`：ubuntu:24.04 + git、curl、tmux、ripgrep、jq、Node 22（給 Agent 跑專案用）。非 root 使用者 agent（uid 1000），WORKDIR /workspace。用官方 `curl -fsSL https://claude.ai/install.sh | bash` 裝 Claude Code。預做首次設定：本機跑一次首次設定，把 ~/.claude.json 裡跟首次設定有關的欄位（不含 key）抄成 `images/agent-base/claude.json` COPY 進去。key 從第 1 步起就不走環境變數：runner 建容器後用 exec 把 key 寫到 `/run/sbx/anthropic_key`（owner agent、0400），`~/.claude/settings.json` 的 `apiKeyHelper` 設 `cat /run/sbx/anthropic_key`——這是第 3 步沿用的同一套，之後只在第 6 步換成 proxy 注入，總共只換一次。PID 1（容器裡第一個程序）用 `sleep infinity`，建容器時開 Init 讓 tini（容器裡負責轉發停止訊號的小程式）轉發 stop 訊號，否則每次 stop 要等 10 秒。留 ARG AGENT 給之後的 codex／harness。驗證：`claude --version`、`claude -p 'say hi'`、`claude -p "create /workspace/hello.txt containing hi" --dangerously-skip-permissions` 後 `cat` 印 `hi`。失敗就先用 `--runtime=runc` 對照，分辨是 gVisor 還是映像檔問題。
3. **Runner daemon**（`runner/`，Go 1.23+，標準庫 `net/http` + Docker 官方 Go client `github.com/docker/docker/client`；第一版就是正式語言，之後不改寫）：所有 Docker 呼叫集中在 `runner/internal/docker/`（adapter），之後換底層（runsc 直驅、Firecracker）都只改這一層並沿用同一組契約測試。`POST /v1/sandboxes`：cpu ≤ 2、memGb ≤ 4，超過回 400（4 vCPU 選項先停用，第 5 步 VDS 換大機後在 `config.yaml` 解鎖）；同時 running ≤ 2，超過回 409。建容器：Runtime runsc、PidsLimit 512、Init true、StopTimeout 5、User agent、Labels `sbx.managed=true`；key 讀 /etc/sandbox-runner.env 後以 exec 寫進 `/run/sbx/anthropic_key`（做法第 2 項），不放 Env。/workspace 掛成 Docker named volume `sbx-ws-<id>`：gVisor 預設把根檔案系統的寫入放記憶體暫存層，容器一停就丟，只有 volume 會真的落地。`GET /v1/sandboxes` 直接查 Docker labels，不另存資料庫（running→Active、exited→Suspend、其他→Error）。stop／start／DELETE（連 volume 一起刪）／exec（非互動，給煙霧測試與 CLI 用）。回收器（**開發期專用**，防止忘了關的容器吃光主機；第 2 步接上控制平面時移除，改由 policy 決定，不是 session 上限）：每 10 分鐘掃一次，running 超過 4 小時 stop、exited 超過 24 小時 remove。單一固定 `Authorization: Bearer $RUNNER_TOKEN`；CORS 只放行 4173；8080 只綁 127.0.0.1；`go build` 出單一執行檔，systemd 常駐。
4. **PTY 串流** `GET /v1/sandboxes/:id/pty`（WebSocket，瀏覽器與伺服器之間的雙向長連線，以下簡稱 ws；這條端點與做法第 5 項的 `src/runner.js` 只服務開發模式，第 3 步改成 ttyd 反代與 `terminal.js` 後作廢）：協定固定不混用——客戶端→伺服器一律 JSON 文字（auth／input／resize），伺服器→客戶端一律二進位（終端輸出），錯誤走 close code。5 秒內沒 auth 就關（4401）；容器不是 running 回 4409。auth 通過後 docker exec `tmux new-session -A -s main`（有 session 就接上、沒有就新建），用 `ContainerExecAttach` 拿到 hijacked 雙向串流；ws 用 `github.com/coder/websocket`。ws 斷線只關串流、不殺 tmux。每沙盒同時只允許一條 ws。測試工具 `runner/cmd/pty-probe`（Go，約 40 行）。
5. **接回雛形**：`npm i @xterm/xterm @xterm/addon-fit`（不用 addon-attach，它的訊框格式跟第 4 條協定不合）。新增 `src/runner.js`，整個模組只在 `import.meta.env.DEV` 啟用，網址與 token 由對話框輸入、存 sessionStorage，不進打包檔、pages.yml 不動。xterm 只建一次，掛在 #app 外的 `#xterm-host`；`detail()` 只留佔位 `<div id="xterm-slot">`，`render()` 結尾 appendChild 搬進去——搬節點不會斷 ws，所以切分頁、搜尋打字不閃。Docker 為真相：載入與每次 Connect 都以 `GET /v1/sandboxes` 重建有 runnerId 的項目。`tick()` 對 runner 沙盒跳過自動降級；Suspend → stop、Resume → start 後重開 ws、Destroy 加 `confirm()`；Files 分頁提示「上傳尚未接到沙盒」。
6. **煙霧測試與 README**：`scripts/smoke.sh`（curl、jq、go run）依序測 400、建立、runsc、exec 五項、pty-probe、stop／start、DELETE，全過印 PASS。在 Anthropic Console 幫這把 key 設每月花費上限（例如 US$50）。README 新增「Runner MVP」一節與目前限制。

**技術選型**

| 選擇 | 理由 |
|---|---|
| KVM 型 Ubuntu 24.04 VPS（4 vCPU / 8 GB） | gVisor 官方支援、不需 /dev/kvm；OpenVZ／LXC 型連 Docker 都跑不起來 |
| Docker Engine + gVisor runsc（systrap） | 建立、限制、停止、volume 全交給 Docker，Suspend／Resume 就是 stop／start；`runsc install` 一行接上 |
| Docker named volume 掛 /workspace | 最無聊的持久化，且跟第 5 步的 volume 對得上 |
| Go 1.23+ + `net/http` + Docker 官方 Go client + `coder/websocket`（runner，第一版即正式語言） | 依 ADR 決定：第 4 步起的 cgroup、netns、runsc、Firecracker 程式都是 Go 生態，一次選定、不改寫；Docker Go client 的 `ContainerExecAttach` 提供 hijack 串流；不採 e2b-dev/infra（綁 Nomad + Firecracker）與 agent-sandbox（綁 K8s）。Firecracker 的 Go SDK 落後上游，第 8 步若用要逐項比對或直接打 HTTP API |
| tmux（容器內）+ xterm.js（自己寫 20 行接線） | 斷線畫面不掉；協定不跟 addon-attach 打架；第 3 步換成 ttyd 反代，xterm.js 保留 |
| key 寫檔 `/run/sbx/anthropic_key` + `apiKeyHelper` | 跟第 3 步同一套，第 6 步才換 proxy；環境變數會被 `env` 與 transcript 帶出去 |
| `vps-setup.sh` 先檢查 cgroup v2、核心 5.6+、XFS reflink 資料碟 | 為第 4、5 步預留，裝機時做完就不用回頭動正在跑沙盒的主機 |
| SSH 本機轉埠（取代 Caddy／網域／TLS） | 一行指令就有加密與身分驗證，這步只有團隊內部用 |
| systemd | daemon 常駐與開機自啟 |

**預估**

1 人 × 3 週 = 主線 10 個工作天 + 風險 5 天。主線裡最容易卡的兩處是 PTY 串流（resize、重連、特殊按鍵，約 4 天）與前端接線（在「每次事件整頁重畫」下保住 xterm 與 ws，約 4 天），都已算在 10 天內；風險 5 天留給 Claude Code 在 gVisor 裡的相容性除錯（2–3 天）與主機、映像檔的意外。超過 3 週就是延期，不再另留。

**驗收**

1. 開通道後 `POST /v1/sandboxes` 帶 memGb:8 → 400；帶 memGb:4 → 回 `{"id":"sbx_xxxxxxxx","status":"Active",…}`。
2. VPS 上 `docker inspect -f '{{.HostConfig.Runtime}} {{.HostConfig.Init}}' $ID` → `runsc true`；`docker volume ls --filter name=sbx-ws-$ID` 有一筆。
3. exec `uname -r` 含 4.4.0、`dmesg | head -1` 含 gVisor、`claude --version` 印版本、`claude -p … --dangerously-skip-permissions; cat /workspace/hello.txt` 印 `hi`；`env | grep -c ANTHROPIC` 印 0、`cat /run/sbx/anthropic_key` 以 agent 身分讀得到。
4. `go run ./runner/cmd/pty-probe $ID` 輸出含 4.4.0。
5. 雛形：Connect runner 後看到 demo 沙盒標示 gVisor · live；Terminal 打 `claude` 直接進畫面；切 Files 再切回不閃；關分頁重開輸出還在。
6. stop → `{"status":"Suspend"}`；start → Active，`cat /workspace/hello.txt` 仍是 hi；DELETE → 204，`docker ps -a --filter label=sbx.managed=true` 與 volume 都空。
7. `npm run build && grep -rl '127.0.0.1:8080\|runnerToken' dist/` 找不到任何檔案。
8. 以上包在 `scripts/smoke.sh`，印 `PASS`。

**風險**

1. gVisor 相容性：Claude Code 是獨立執行檔，可能踩到未實作的系統呼叫；先用 runc 對照。
2. 效能：systrap 每個系統呼叫都攔，npm install、clone 大 repo 會慢；之後有 /dev/kvm 再加 `--platform=kvm`。
3. 只有 /workspace 會留下：~/.claude 對話紀錄、全域套件 Suspend 後消失，README 要寫清楚（第 5 步把家目錄也放 volume）。
4. Docker checkpoint 是實驗功能，第 4 步可能要改成直接呼叫 runsc；所以 Docker 呼叫鎖在一個檔案。
5. 安全：單一共用 token、容器可連任何網路、API key 以檔案放在容器內（Agent 讀得到）。圍欄是 8080 只綁本機、只經 SSH 通道、Pages 永遠是模擬、key 設花費上限；只能團隊內部用。
6. Docker socket 等於 root：daemon 以專用使用者跑。
7. 8 GB 主機最多 2 個 4 GB 沙盒；主機 OOM（記憶體用光）殺掉容器時前端要顯示 Suspend／Error 而不是當掉。
8. SSH 通道斷線 ws 會斷，前端要能自動重連，驗收容易漏測。
9. .claude.json 欄位隨版本變：映像檔鎖 claude 版本。

**這一步先不做**

記憶體快照 checkpoint／restore；Idle 與閒置偵測；網域、TLS、Caddy；登入、多使用者、資料庫；可安裝的 CLI；檔案上傳進沙盒、從 repo 建立；用量計費；祕密注入 proxy 與出口白名單；Firecracker；Codex／Harness 映像檔；多條 ws 協作；多把 token。

### 3.2 control-plane：控制平面（3.5 週）

**目標**

讓雛形的沙盒清單、狀態、倒數與用量離開瀏覽器，改由一台 VPS 上的 API 與 Postgres 記住；用 GitHub 帳號登入；發 API token 讓之後的 CLI 能接上；狀態表與 Runner 介面現在就預留 Idle 與中間態，之後接真 VM 不用改路由與資料表。

**做完會看到**

1. 打開 `https://console.<你的網域>`，按「Sign in with GitHub」，看到跟現在幾乎一樣的 Sandboxes 頁；側欄是你的 GitHub 頭像與「<login>'s workspace」。三個示範沙盒都在（都是 Suspend、標「示範資料」，Usage 頁保留原本時數）。
2. New sandbox、Set idle／Suspend／Resume 都能用；在終端打字，詳情頁倒數重置。換一台電腦或手機登入，看到同一份清單、同一個倒數；兩邊同時操作不會跳錯誤。
3. Quick start 頁多「API tokens」：Create token 拿到 `sbx_...`，用 curl 打 `/v1/sandboxes` 拿到同一份清單；但 token 不能拿來生新 token。
4. 第二個 GitHub 帳號登入是空清單。push 到 main 一分鐘內正式站自動更新；VPS 每天自動備份資料庫到另一處。
5. 注意：這步先用假的 runner，Active／Idle／Suspend 只是資料庫紀錄，畫面會標「runner 未接」；第 1 步做好的 runner 要到第 3 步開頭才接進控制平面（只加一個 `http.ts`）。header 的「Prototype」pill、footer「Browser-local demo」、demo-card「LOCAL PREVIEW」三處文案在這步改成環境標籤（dev／prod）。

**做法**

1. **環境準備（做法第 1 項，創辦人可先做）**：買網域，固定只用 `console.<網域>`（API 與之後的 install.sh 都同源，不另開 `api.<網域>`）；VPS Ubuntu 24.04、2 vCPU / 4 GB，裝 Docker + compose、Node 22、git、rclone，`ufw` 只開 22/80/443；DNS A 記錄指到 VPS（`dig +short console.<網域>` 檢查）；建 `deploy` 使用者（在 docker 群組、不給 sudo），CI 用的 SSH 金鑰加 forced command（這把鑰匙只能執行 `/opt/sandbox/bin/deploy.sh`，拿到私鑰也開不了 shell）；祕密檔 `/opt/sandbox/.env`（權限 600，不進 git）；開兩個 GitHub OAuth App（OAuth＝用 GitHub 帳號登入、我們不存密碼），本機與正式各一；GitHub repo secrets 放 `DEPLOY_SSH_KEY`、`VPS_HOST`；開一個物件儲存 bucket（Cloudflare R2 或 S3）給備份，`rclone config` 設 remote `backup`。
2. **api/ 骨架與資料表**：同一個 repo 新增 `api/`（hono、drizzle-orm、postgres、vitest）。`deploy/docker-compose.yml` 只放 postgres:16 且不寫 `ports:`（公網碰不到）。Drizzle 宣告 7 張表：users、sessions（只存 SHA-256 雜湊，單向指紋，從指紋算不回原值）、workspaces（policy 欄位就放這裡：idle_after_s 預設 120、suspend_after_s 預設 300、agent_busy_max_s 預設 7200、max_sandboxes 預設 3；之後步驟只加欄位不另建 policy 表）、workspace_members、api_tokens、sandboxes（id 沿用 `sbx_` + 8 碼；status 用 text 不用 enum；名稱唯一用 partial unique index，刪掉 test-1 後可再建 test-1）、sandbox_events。**`sandbox_events` 在這步一次定案，後續步驟只加 kind、不加表**：append-only（`revoke update, delete`）、kind（created／active／idle／suspended／resumed／resized／lost／destroyed；第 4 步起 suspended 帶 `mode: cold|warm`）、state、vcpu、mem_gib、disk_gib、snapshot_gib、`at default clock_timestamp()`（只由 Postgres 蓋，請求裡沒有 at）、source、`idem_key unique`、reason、`resume_ms` nullable、runtime。`api/src/state.ts` 一份狀態表（哪個狀態可以變成哪個）：`TRANSITIONS = { Active:['Idle','Suspend'], Idle:['Active','Suspend'], Suspend:['Active'], Error:['Active','Suspend'] }`，Suspending／Resuming 先佔位。狀態切換的路由固定一條 `POST /v1/sandboxes/:id/state {status, reason}`，之後步驟不再另開 `/idle|/suspend|/resume`。`GET /healthz` 真的 `SELECT 1`。
3. **GitHub OAuth 與 session**：手寫兩支路由（redirect → 換 code → 打 /user，約 60 行）；第一次登入建個人 workspace。cookie `sbx_session` 放明文 id、資料庫存 SHA-256(id)、30 天到期；HttpOnly + SameSite=Lax，正式加 Secure。`GET /v1/me`、`POST /auth/logout`；過期 session 由 api 每 24 小時 DELETE。
4. **認證中介層與租戶隔離**：`requireAuth`（cookie 或 Bearer token）與 `requireSession`（只認 cookie；`/v1/tokens/*` 與 `PATCH /v1/workspace` 掛它，所以 CLI token 外洩也不能生新 token、改 policy）。資料庫存取全走 `api/src/db/repo.ts`，每個函式第一個參數都是 `workspaceId`，查不到回 404；`api/scripts/no-db-in-routes.sh` 一行 grep 擋路由檔直接 import db，掛 pretest 與 CI。測試用第二個 database `sandbox_test`：`isolation.test.ts`（B 的 token 打 A 的沙盒要 404）、`state.test.ts`（狀態表每一格走一遍）。
5. **沙盒生命週期**：`POST/GET/DELETE /v1/sandboxes`、`POST /v1/sandboxes/:id/state {status, reason?}`（先查狀態表，不合法 409；合法就 `await runner.setTier()`，成功才更新並寫事件；runner 丟錯就 Error、回 502）。`reason:'auto-demo'`（瀏覽器倒數到期）多一道伺服器檢查：`now - last_activity_at` 未到就 409，舊分頁不會把別台裝置正在用的沙盒降級。`POST /v1/sandboxes/:id/touch` 更新活動時間，Idle 就轉回 Active。每個沙盒回應附伺服器算的 `seconds:{Active,Idle,Suspend}`。建立沙盒前檢查 `workspaces.max_sandboxes`（預設 3，超過回 409）；登入與建立路由加最簡單的 rate limit（每 IP 每分鐘 N 次，記憶體計數即可，半天）。Runner 介面 `create / setTier / destroy` + `fake.ts`（只寫一筆「runner=fake」事件），`RUNNER_DRIVER=fake`；第 3 步接真 runner 時只加 `http.ts`。刪掉第 1 步 runner 的開發期回收器（4 小時 stop／24 小時 remove），從此沙盒何時停由 policy 決定。`npm run db:seed` 塞三個示範沙盒（全 Suspend、回填事件讓 Usage 時數跟雛形一樣）。
6. **前端改接 API**（換資料來源不重寫 UI）：
   - 資料來源：新增 `src/api.js`（401 切登入畫面、409 重抓再 render 不跳錯）。`src.js` 啟動 `GET /v1/me` + `GET /v1/sandboxes`；刪掉 `save()`、`savePolicy()`、localStorage 的 `sandbox-v1`／`sandbox-policy`。從這步起前端只有一種模式（吃 API），不保留純瀏覽器模擬；GitHub Pages 凍結在改接前的最後一版當展示。
   - 倒數：以伺服器 `last_activity_at` 為基準，終端每次送指令呼叫 touch（10 秒最多一次）；`tick()` 每 30 秒重抓校正，到期改打 state 帶 `auto-demo`（過渡，第 4 步第一件事就是刪掉）。
   - 畫面標示：badge 加 Suspending／Resuming 轉圈、Error 紅色、「runner 未接」小字、「示範資料」標籤；header／footer／demo-card 的 Prototype、Browser-local demo、LOCAL PREVIEW 改成環境標籤（dev／prod）。Files 頁提示「檔案暫存於此瀏覽器」。Quick start 加 API tokens 段。Snapshot／Fork 先 disabled。
   - 設定檔：`vite.config.js` 的 `base` 改 `process.env.BASE ?? '/'`，`server.proxy` 轉 8787。同一個 PR 改 README「資料與限制」與 research.md 第 53 行。
7. **部署與備份**：compose 三服務 postgres + api（啟動前跑 migrate）+ caddy:2（同網域反向代理 `/v1/* /auth/* /healthz` 到 api:8787，其他路徑 file_server `dist/`（第 3 步的 `install.sh` 也放這裡），自動申請 HTTPS）。`deploy.sh`：git reset → npm ci && build → compose up → curl healthz。GitHub Actions 只有一步 ssh；`pages.yml` 改成只剩 `workflow_dispatch`，GitHub Pages 凍結。crontab 每天 03:00 `pg_dump | gzip` → `rclone copy` 到 bucket → 保留 30 天（這是全計劃唯一一套 Postgres 備份，第 7 步只加新鮮度檢查與失敗告警）；第一次部署後做一次還原演練。

**技術選型**

| 選擇 | 理由 |
|---|---|
| Node 22 + TypeScript（api/）+ Hono | 跟前端同語言；十幾支 endpoint 夠用，換 Fastify 也只是幾十行 |
| PostgreSQL 16（不對外開 port） | 之後 runner（另一台）與計費要共用同一份權威狀態；e2b 也是 Postgres |
| Drizzle ORM + drizzle-kit | 資料表用 TypeScript 宣告、migration 自動產生，SQL 看得懂 |
| status 用 text + `state.ts` 一份狀態表 | 之後加 Suspending／Resuming 只改一處，不用 migration |
| GitHub OAuth 手寫、session 與 API token 都只存 SHA-256 | 三步流程套件反而多一層；備份外洩也冒用不了；不需要 SESSION_SECRET |
| Runner 介面 create / setTier / destroy + fake driver | 第 3 步接上第 1 步的 runner 只加一個 http.ts，路由與資料表不動 |
| `sandbox_events` 一次定成第 7 步要的形狀、policy 只放 `workspaces`、狀態切換只有一條 `/state` 路由 | 第 4、7 步只加 kind 與欄位，不加表、不改路由，前端不用改接兩次 |
| Caddy 2 + Docker Compose | 一個 Caddyfile 搞定 HTTPS 與同源；單台 VPS 最無聊的部署法 |
| SSH forced command + VPS 上的 deploy.sh | CI 只有一把「只能跑一支腳本」的鑰匙；比 rsync 少一個工具 |
| cron + pg_dump + rclone | 三行 shell 就有每日異地備份 |
| 借 e2b 的 API 形狀與資料表概念，不搬程式碼 | 它綁 Nomad + Consul + GCP，1–2 人拆不動；自己寫約 1,500–1,800 行比拆快 |

**預估**

1 人 × 3.5 週。做法第 1 項（環境準備）半週（多半是等 DNS、開帳號，創辦人可先做）；週 1 骨架、資料表、登入、token、測試；週 2 生命週期、沙盒數上限與 rate limit、Sandboxes 頁改接；週 3 其餘畫面、部署、備份。最花時間的是前端改接：每個動作都變成「送出 → 等回應 → 重抓 → 重畫」，要一個畫面一個畫面對照舊版點過。

**驗收**

1. `ssh -i deploy_key deploy@<VPS> whoami` 印出的是 deploy.sh 的輸出，不是 `deploy`。
2. `curl -s https://console.<網域>/healthz` 回 `{"ok":true,"db":"up","version":"<commit>"}`；`nc -zv -w3 console.<網域> 5432` 連線失敗。
3. GitHub 登入後三個示範沙盒都是 Suspend 帶「示範資料」；Usage 頁 frontend-playground 的 Active 約 20m40s。
4. 建 `test-1` → Active、「runner 未接」、Activity 有 created 與 runner=fake；另一台裝置倒數相差不超過 2 秒。
5. 用 token：`curl -H "Authorization: Bearer $T" $H/v1/sandboxes | jq -r '.[].name'` 印四個名稱；POST state Suspend → 印 Suspend；再 POST Idle → 409；用 token POST `/v1/tokens` → 403。
6. 另一個 GitHub 帳號清單是空的，打別人的沙盒 → 404。
7. 兩個分頁同時倒數到期都變 Idle、無錯誤（一個 200、一個 409 後重抓）。
8. 刪掉 test-1 再建 test-1 成功。
9. `npm test` 兩支測試綠燈；故意在路由檔 import db/client → pretest 紅燈。
10. `/opt/sandbox/backups/` 有今天的 `.sql.gz`，`rclone ls backup:sandbox-backups` 看得到；灌進本機 Postgres 後登入看到同一份沙盒。
11. 改一行前端 push 到 main → 一分鐘內正式站更新，`/healthz` 的 version 是新 commit。
12. 建第 4 個沙盒 → 409 `max_sandboxes`；同一 IP 一分鐘內連打登入路由 → 429。

**風險**

1. 租戶隔離只靠應用層 WHERE workspace_id：repo.ts 集中 + grep 守門 + 隔離測試；Postgres RLS 留到之後。
2. 沒有真 VM，使用者可能誤會已經在跑：UI 標「runner 未接」、示範沙盒標「示範資料」。
3. Suspending／Resuming／Error 只是佔位，真正的問題到第 3 步接上真 runner 才冒出來；只有 runner/ 與 state.ts 要動。
4. 瀏覽器倒數的 auto-demo 只是過渡：伺服器用 last_activity_at 再檢查一次。
5. src.js 單檔重構容易弄壞既有示意功能：先做 api.js 抽換資料來源，每個畫面改完對照 Pages 版點一遍。
6. OAuth App 本機／正式兩組容易搞混；cookie Secure 旗標依 NODE_ENV 切換。
7. deploy 使用者在 docker 群組等同 root：forced command 只能跑 deploy.sh；VPS 只做這一件事。
8. 在 VPS 上 build 前端吃 CPU：2 vCPU 夠用，太慢再改 CI build。
9. .env 外洩＝OAuth secret 外洩：換 secret 即可，DB 只有雜湊。
10. 單台 VPS 沒有備援：每日 pg_dump，最多掉一天。

**這一步先不做**

真的建立 gVisor 容器（第 1 步）；把第 1 步的 runner 接進來（第 3 步開頭）；終端串流與 CLI（第 3 步）；伺服器端閒置偵測（第 4 步）；檔案上傳到伺服器（第 5 步）；真實計費（第 7 步）；Snapshot／Fork；多人 workspace；其他登入方式；Postgres RLS、精細的 rate limiting、OpenAPI；自動還原測試與告警（告警在第 7 步做法第 7 項）；把 e2b-dev/infra 整套搬進來；GitHub Pages 與新版同步。

### 3.3 cli-terminal：CLI 與終端串流（5 週，分 A／B 兩段）

**目標**

先把第 1 步的 runner 接進第 2 步的控制平面（console 按 New sandbox，VDS 上真的多一個容器），再讓使用者在自己電腦打 `sandbox claude --repo URL`，10 秒內接上雲端沙盒的終端、看到 repo 正在 clone，clone 完自動出現 Claude Code 提示；關掉終端再 `sandbox connect` 畫面還在；console 的 Terminal 分頁（B 段）看到同一個畫面。

**做完會看到**

1. **第 1 週末**：登入 `console.<網域>` 按 New sandbox，狀態變 Active、「runner 未接」小字消失；VDS 上真的多一個容器（工程師用 `docker ps` 確認）。push 到 main 一分鐘內，VDS 的 runner 與沙盒映像檔也自動更新。
2. **第 2 週初**：創辦人本機 `docker run` 沙盒映像檔，瀏覽器開 http://localhost:7681，看到 tmux 裡先跑 git clone、接著直接是 Claude Code 提示，中間沒有選主題、確認 key、信任資料夾三個問答。
3. **第 4 週末（A 段，CLI）**：Mac 上 `curl -fsSL https://console.<網域>/install.sh | sh`，`sandbox login` 貼 token，`export ANTHROPIC_API_KEY=…; sandbox claude --repo https://github.com/<公開 repo>`。10 秒內本機終端就是沙盒的 tmux，看得到 clone 進度；clone 完自動進 Claude Code。CLI 印一行瀏覽器連結與「脫離鍵 Ctrl-\」。Ctrl-\ 脫離 → `sandbox ls` 仍 Active → `sandbox connect <id>` 回到剛才的畫面；`sandbox suspend` 後再 connect 印 Resuming… 然後接回。雛形首頁 QUICK LAUNCH 的複製按鈕改成複製「安裝 + 啟動」兩行。建立表單的 agent 下拉：Claude 正常、Codex 標「盡力支援」、Harness 灰掉（等第 5 節第 1 點定案）。
4. **第 5 週（B 段，瀏覽器）**：console 詳情頁 Terminal 分頁換成真的 xterm.js。登入後從清單點進沙盒（或點 CLI 印的連結）→ 看到跟本機一模一樣的 tmux 畫面，兩邊同步；「Demo session」改成 Connecting／Live／Reconnecting／Suspended；Suspended 時分頁內有一顆真的 Resume。若前四週延誤，B 段整個移到下一步。

**做法**

0. **（A）把第 1 步的 Go runner 接進控制平面**（2–3 天）：runner 的 API 形狀不變（create／stop／start／destroy／exec／list），改綁 `10.8.0.2:9000`（只在 WireGuard 上），並補一組控制平面對 runner 的契約測試；第 1 步的 PTY 端點與 `src/runner.js` 作廢，由做法第 3 項的 ttyd 反代與第 7 項的 `terminal.js` 取代；映像檔 entrypoint 改 ttyd；key 檔案注入沿用。控制平面加 `api/src/runner/http.ts`：create／setTier／destroy 打 `http://10.8.0.2:9000`，`RUNNER_DRIVER=http`；runner 建立／停止失敗回 502 並標 Error；runner 啟動時回報既有沙盒對照 DB（多的標 Lost、少的補建紀錄）。這項做完第 1 步的「runner 未接」就消失。
1. **（A）沙盒映像檔**：`apt install -y ttyd tmux git curl`（ttyd＝把任何指令包成網頁終端的小工具）；Node 22 → `npm i -g @openai/codex`；Claude Code 用官方安裝器，`DISABLE_AUTOUPDATER=1`。`~/.tmux.conf` 加 `set -g window-size latest`、`history-limit 50000`。`ENTRYPOINT ["ttyd","-p","7681","-W","tmux","new","-A","-s","main","-c","/workspace"]`；容器用 `--init`。金鑰沿用第 1 步：runner 用 exec 把 key 寫到 `/run/sbx/anthropic_key`（owner agent、0400）。`sbx-agent-setup <agent>` 把所有「會隨版本變」的設定集中一檔：Claude 寫 `~/.claude.json`（hasCompletedOnboarding、theme、projects./workspace.hasTrustDialogAccepted）與 `~/.claude/settings.json` 的 `apiKeyHelper`（`cat /run/sbx/anthropic_key`）；Codex `codex login --with-api-key` + config.toml `trust_level = "trusted"`。`sbx-agent-start <agent> [repo]`：`tmux new -d -s main`，有 repo 則 `git clone --depth 1 $2 . && claude`，用 `tmux send-keys` 送進去（agent 結束或 clone 失敗 shell 還在，看得到錯誤）；建立表單與 CLI 的 repo 欄位從這步起就傳進 create body，這就是「從 repo 建立」的實作，第 5 步只換磁碟不重做。映像檔 CI：起容器、寫假 key、跑 start、睡 10 秒、`tmux capture-pane` 必須出現提示符且不出現 theme／trust 字樣、`env` 不含 ANTHROPIC。
2. **（A）兩台主機接線**：WireGuard（Linux 內建的點對點加密隧道）VPS 10.8.0.1、VDS 10.8.0.2；runner 只綁 `10.8.0.2:9000`。沙盒之間斷網：`docker network create -o com.docker.network.bridge.enable_icc=false sbx`。網域與反代沿用第 2 步的 Caddy（`console.<網域>` 同源），只加 `/v1/sandboxes/:id/terminal` 走同源 wss；不另開 `api.<網域>`、不加 CORS。
3. **（A）Runner 終端轉發** `GET /sandboxes/{id}/term`：查沙盒 IP，用 Go 標準庫 `httputil.ReverseProxy` 轉到 `http://<ip>:7681/ws`（Go 1.20 起原生轉 WebSocket）。非 Active 回 409 + `{"state":…}`。這步**不記** last_input_at：ttyd 每 5 秒 ping、resize 都是位元組，看位元組永遠不閒置；閒置留給第 4 步用 tmux 的 `#{session_activity}`。驗：`websocat -b --protocol tty ws://10.8.0.2:9000/sandboxes/<id>/term`。
4. **（A）Control plane 終端入口**（Hono 路由，Node 端用 `ws` + `http-proxy` 或手寫 pipe，不寫 Go）：`POST /v1/sandboxes/{id}/terminal-ticket`（瀏覽器開 WebSocket 不能自訂標頭，所以發 60 秒一次性票，非 Active 直接 409；瀏覽器用第 2 步的 cookie session 換票，CLI 用 Bearer）；`GET /v1/sandboxes/{id}/terminal` 接 Bearer 或 `?ticket=`，再 pipe 到 runner 的 `/term`；log 要遮 `ticket=`。Resume 走第 2 步同一條 `POST /v1/sandboxes/{id}/state {status:'Active'}`，這步起改回 202（非同步版本，客戶端輪詢到 Active）。ttyd 協定備忘：子協定 `tty`、二進位訊息、先送 `{"columns","rows"}`、客戶端 `'0'+輸入`／`'1'+resize`、伺服器 `'0'+輸出`。
5. **（A）`sandbox` CLI**（Go + cobra + coder/websocket + x/term）：`login`（token 存 `~/.config/sandbox/config.json` 0600）、`claude|codex|harness [--repo] [--cpu]`（從本機環境變數讀 key 放進 create body，輪詢到 Active 後 attach）、`ls`、`connect <id>`（Suspend 就先 resume）、`suspend`、`snapshot`、`exec <id> -- <cmd>`（非互動，打 runner 的 exec，給驗收與腳本用）。attach：`term.MakeRaw` 進 raw mode（Ctrl-C 直接送進沙盒而不是殺掉 CLI），任何退出路徑都 `term.Restore`；監聽 SIGWINCH 送 resize；脫離鍵 Ctrl-\（0x1c，不跟 tmux 的 Ctrl-B 衝突）。重連：1s、2s、4s… 上限 15s、最多 5 分鐘；409 印 `Sandbox is suspended. Run: sandbox connect <id>` 退出碼 2。單元測試用 httptest 起假 ttyd 驗協定前綴。
6. **（A）發佈與部署**：(a) CLI：goreleaser 以 `cli/v*` tag 產 darwin/linux × amd64/arm64 推 GitHub Releases；`install.sh` 判斷 `uname -s/-m` 下載到 `/usr/local/bin/sandbox`，放在 `https://console.<網域>/install.sh`（第 2 步 Caddy 的 file_server 直接服務）。(b) 映像檔：CI 通過後 push `ghcr.io/<org>/agent-base:<git-sha>`，runner 設定檔釘 tag，Claude Code 版本也記在 tag 對應的 Dockerfile 裡（這就是「鎖版本」的規則）。(c) runner：`infra/vds-deploy.sh` 用跟第 2 步一樣的 forced-command SSH 金鑰，更新 runner 二進位與映像 tag 後 `systemctl restart sandbox-runner`；GitHub Actions 加第二個 job，之後第 4–6 步每次改 runner 都走這條。(d) 雛形 `[data-copy]` 改複製安裝 + 啟動兩行，拿掉「CLI 尚未實作」；`guide()` 改成安裝說明。README 新增「安裝 CLI」與「終端串流架構：CLI／瀏覽器 → Caddy → VPS API → WireGuard → VDS runner → 沙盒 ttyd + tmux」。
7. **（B）console Terminal 分頁換真終端**：新檔 `terminal.js` 取代第 1 步開發模式的 `runner.js`，用模組變數保存單例 `{id, term, fit, ws, container, status}`，`mount(sandboxId, el)` 同一個 id 只 appendChild 回去並 fit()，不重連；`render()` 每次整頁重寫 innerHTML，所以不能直接寫進 `detail()`。從已登入的沙盒清單點進去就連（cookie session 換 ticket，不用貼 ID、不用 token 欄位）；CLI 印的連結 `#t=<id>` 只是直接開到該沙盒。每次重連都重新 POST 一張 ticket；409 → Suspended 並顯示「Resume sandbox」按鈕。

**技術選型**

| 選擇 | 理由 |
|---|---|
| ttyd + tmux（沙盒內） | Ubuntu 套件庫就有；省掉自己寫 pty 常駐程式；tmux 也記錄最後一次按鍵時間，第 4 步直接拿來當閒置訊號 |
| 沿用第 1 步的 Go runner，只加 WireGuard 綁定與契約測試 | 語言在 ADR 已定案，這步沒有改寫；adapter 邊界不動 |
| Docker network icc=false | 一行設定沙盒之間互相連不到 |
| WireGuard | VPS 與 VDS 不在同一供應商也能安全互通；多台 runner 只是多一個 peer |
| 沿用第 2 步的 Caddy（同源） | 不另開網域、不加 CORS；WebSocket 免額外處理 |
| Runner 端 Go 標準庫 ReverseProxy、控制平面端 Hono + `ws` pipe | 各用自己語言的標準做法，不為了代理再引一種語言 |
| Go + cobra + coder/websocket + x/term | 單一靜態執行檔，使用者不用先裝 Node 或 Python |
| @xterm/xterm + @xterm/addon-fit | ttyd 自己的網頁也用它 |
| Claude Code apiKeyHelper、Codex `--with-api-key` | 官方支援的方式，可事先寫設定檔跳過首次問答，key 不放環境變數（第 1 步同一套） |
| ghcr.io 映像檔以 git-sha 為 tag、runner 釘 tag、`vds-deploy.sh` 走 forced-command SSH | 跟第 2 步同一套部署觀念；「鎖 Claude Code 版本」有可指的東西 |
| goreleaser + GitHub Releases、`install.sh` 由 console 同源服務 | 一個 yaml 搞定四平台；安裝網址不用再想 |

**預估**

1 人 × 5 週：runner 接進控制平面 2–3 天（做法第 0 項，含 http.ts、契約測試與部署腳本），原本預留給改寫的其餘 2–3 天改為 CLI 邊角與 ttyd 除錯的緩衝；映像檔與免問答設定 4 天；接線 1 天；runner 轉發 1 天；control-plane 終端入口 2 天；CLI 6 天；發佈與 registry 2 天；瀏覽器終端 3–4 天（第 5 週，可整項延到下一步）。最花時間的是 CLI attach 的邊角（raw mode 還原、Ctrl-C 透傳、視窗大小、重連、409）；其次是 Claude Code／Codex 設定檔格式追蹤，以及 ttyd + tmux 在 gVisor 裡的除錯（要改寫成 creack/pty 常駐程式再 2–3 天，是第 5 週的緩衝來源）。

**驗收**

0. console 登入後按 New sandbox → Active、無「runner 未接」；VDS `docker ps` 看到容器；停掉 runner 再按 → Error 且 API 回 502。改一行 runner push 到 main → 一分鐘內 VDS `systemctl status sandbox-runner` 顯示新版本、`docker images` 有新 tag。
1. 乾淨的 Mac：`curl -fsSL https://console.<網域>/install.sh | sh` → `sandbox --version` → `sandbox login` 印 `Logged in`。
2. `sandbox claude --repo <公開 repo>` → 印 `Sandbox sbx_xxxx · browser: …#t=sbx_xxxx` 與 `Detach: Ctrl-\`；10 秒內看到 clone 進度；clone 完自動出現 Claude Code 提示，沒有任何問答；`!env | grep -c ANTHROPIC` 印 0。
3. Ctrl-\ → 印 Detached，本機終端正常不用 `reset`；`sandbox ls` 顯示 Active；`sandbox connect` 回到相同畫面。
4. `sandbox suspend` → `sandbox ls` 顯示 Suspend；`sandbox connect` 印 `Resuming…` 後接回，Claude Code 仍在。
5. attach 中拔 Wi-Fi 10 秒 → 印 `[sandbox] reconnecting…` 自動恢復；另一終端 suspend → 原終端印提示並退出碼 2。
6. 隔離：沙盒 A `curl -m 3 http://<B 的 IP>:7681` 逾時；公網 `curl -m 3 http://<VDS 公網 IP>:9000` 逾時。
7. （B）登入 console 從清單點進沙盒（或開 `…/#t=<id>`）→ Terminal 分頁跟本機一模一樣、右上角 Live；搜尋框打字、切分頁不閃不重連；suspend 後出現「Resume sandbox」，按下 Connecting → Live；DevTools 每次重連都有新的 terminal-ticket 請求，沒有任何 localStorage token。
8. `sandbox exec <id> -- ls /workspace` 印出 clone 下來的檔案。

**風險**

1. ttyd 在 gVisor 遇到 pty 或 epoll 相容問題：退路是 Go creack/pty 寫約 150 行同協定的常駐程式，已預留 2–3 天。
2. Claude Code 與 Codex 設定檔格式隨版本變：集中一檔 + CI 檢查，映像檔關自動更新，版本釘在 ghcr tag 對應的 Dockerfile。
3. API key 仍以檔案放沙盒內，Agent 讀得到：只減輕沒解決，第 6 步換 proxy 注入。
3a. 語言已在 ADR 定案為 Go，這步沒有改寫風險；接線用第 1 步的煙霧測試 `smoke.sh` 與新加的契約測試守住 API 形狀。
4. Suspend → Resume 後沙盒內舊 TCP 全部失效：客戶端一定要主動重連。
5. ticket 放 query string：只走 wss、60 秒、一次即作廢；Caddy 與 control-plane log 要遮掉。
6. WireGuard 被供應商防火牆擋 UDP：多半天調 port 或 PersistentKeepalive。
7. harness 尚未定義是哪個工具，目前只是 bash 殼。
8. Codex 需要 Node 22，映像檔多約 100 MB。
9. tmux 兩個大小不同的終端同時接上以最新者為準，另一邊會重排，README 寫一句。
10. git clone 時間不在我們控制內，所以驗收是「10 秒內接上並看到 clone 進度」。

**這一步先不做**

閒置判斷與自動降級（第 4 步用 tmux `#{session_activity}`）；vsock 傳輸；API key vault／proxy 注入與出口白名單（第 6 步）；檔案上傳同步與 volume（第 5 步）；`sandbox ssh`、port forwarding、預覽網址、終端錄影（整份計劃都不做，第 6 步的去識別只針對連線紀錄與 API 日誌）；agent 的 OAuth 登入；Windows 版、Homebrew、自動更新；沙盒內的 `sandbox` 指令；多 runner 路由；ttyd 每沙盒密碼。

### 3.4 auto-tiering：自動降級（5 週，分 A／B 兩段）

**目標**

真實沙盒沒人敲鍵盤、Agent 做完事在等人時，自己從 Active 降到 Idle 再到 Suspend；Agent 自己在跑長任務時不會被誤暫停；使用者一連回來就原地接續。A 段的 Suspend 是冷的（停容器、留檔案，第 1 步就有），B 段升級成記憶體快照（回到同一個畫面）；B 段做不通，冷 Suspend 就是正式行為。

**做完會看到**

1. **A 段（第 1 週末）**：沙盒詳情頁顯示由伺服器算出的「auto-idle in 1:58」倒數；瀏覽器分頁一直開著不動，倒數歸零徽章自己變 Idle，Activity 多一行「No keyboard input 2m · CPU 1% → Idle (auto)」（工程師在主機上可確認 CPU 已被限速）。再放著不管，徽章變 Suspend（冷：容器停了、檔案還在），Activity 記「Idle 5m → Suspend (auto, cold)」；`sandbox connect` 重開容器回到新的 shell，`/workspace` 檔案都在。回終端打一個字，1 秒內有反應、徽章跳回 Active。Usage 頁兩個下拉選單改成真的會改伺服器 policy。沙盒裡執行 `sandbox-agent done`（Claude Code 完成回應時自動打）30 秒內降 Idle；`sandbox-agent busy` 後詳情頁顯示「suspend held · agent busy」。
2. **B 段（第 5 週末）**：放著不管徽章再變 Suspend 時，沙盒真的不在跑了、記憶體已存成一個檔（工程師可在主機確認）。`sandbox connect <id>` 印「Resuming from snapshot… 3.2s」，同一個 tmux 畫面連捲動歷史回來。恢復失敗或主機重開過，徽章顯示 Suspend(error)／Lost，多一顆「Start fresh from workspace」按鈕用原本的 /workspace 冷開機。Suspend 影像在詳情頁顯示「保留至 <日期>」（預設 30 天）。README 多一張 1／2／4 GB 沙盒的 checkpoint／restore 秒數表。

**做法**

1. **（A）閒置訊號收集器** `runner/internal/idle/collector.go`，每 10 秒對每個沙盒產出 `Signals{last_pty_input_at, last_pty_output_at, cpu_util, cpu_demand, agent_busy_at, agent_done_at}`。PTY 拆兩個方向：只有「鍵盤→沙盒」才算有人在用；「沙盒→畫面」只顯示不參與判斷（tmux 狀態列時鐘、Claude Code 轉圈圈都會一直有輸出）。映像檔 `~/.tmux.conf` 加 `set -g status-interval 0`。CPU 讀 cgroup（Linux 限制與統計一組程序資源的機制）的 `cpu.stat`，< 5% 算安靜；`cpu_demand` 用嚴格定義：連續兩個 10 秒窗口 `throttled_usec` > 50% 或利用率 > 30%。Agent hook（Agent 在特定時機自動執行的小指令）：Claude Code 的 `UserPromptSubmit`／`PreToolUse` → `sandbox-agent busy`，`Stop` → `sandbox-agent done`；Codex 的 `notify` → done。`sandbox-agent` 的傳輸方式明定：runner 在沙盒閘道位址（這步是 bridge 閘道；第 6 步起固定 `10.77.0.1`）開 `:9001`，只收 `POST {busy|done}`，沙盒身分以來源 IP 判定，不帶 token；第 6 步的防火牆規則要放行這個埠。快速反應：bridge 收到鍵盤位元組或 busy 就直接呼叫同機 runner 的 `SetTier(id, Active)`，不等 10 秒輪詢。
2. **（A）狀態機、policy 與 Idle 限速**：純函式 `Next(state, signals, policy, now) (state, reason, hold)`，規則全寫成 table-driven 測試。Active→Idle：無鍵盤輸入 ≥ `idle_after_s` 且 CPU 安靜 ≥ 60 秒，或 `agent_done` 後 30 秒。Idle→Active：鍵盤、`cpu_demand`、busy hook、connect、API resume；Idle 最短停留 30 秒。Idle→Suspend：Idle ≥ `suspend_after_s` 且 Agent 不在 busy（busy 比 done 新且 < `agent_busy_max_s` 預設 7200 秒，防 hook 漏打卡死）；被擋回 `hold="agent_busy"`。Idle 實作：寫 `cpu.max` = `<quota> 100000`（起點 0.1 顆，做法第 4 項的可行性試做量過再定），Active 寫回 `max`；故意不用 `runsc pause` 凍結，因為凍結會讓等 LLM 的回應收不到。control-plane **不加新表**：policy 沿用第 2 步 `workspaces` 的 `idle_after_s`／`suspend_after_s`／`agent_busy_max_s`，端點維持 `PATCH /v1/workspace`；事件沿用 `sandbox_events`，只補 kind 與 reason；`GET /v1/sandboxes/{id}` 多回 `state, idle_since, next_transition_at, last_reason, hold`；狀態切換維持 `POST /v1/sandboxes/{id}/state {status, reason}`。Lost 與 watchdog 只在這步定義（做法第 7 項），第 7 步只寫「Lost 段計 0」。reason 固定用 `pty_idle+cpu_idle`、`agent_done`、`idle_timeout`、`input`、`cpu_demand`、`agent_busy`、`connect`、`manual`、`cold_start`、`disk_full`、`lost`。
3. **（A）冷 Suspend、接回雛形與 CLI**：A 段的 Suspend 就是第 1 步的 stop 容器、留 volume，事件 `suspended{mode: cold}`；Idle→Suspend 的自動轉換在 A 段就以冷 Suspend 生效，Resume 是 start 容器重開 tmux（畫面重來）。`src.js` 拿掉 `tick()` 本機降級與第 2 步的 `auto-demo` 過渡，改每 5 秒 `GET /v1/sandboxes/{id}`；倒數用 `next_transition_at`；Activity 列 `sandbox_events`；Usage 頁下拉改打 `PATCH /v1/workspace`（選項值不變）；Set idle／Suspend／Resume 都打 `/state`。B 段做完，同一顆 Suspend 按鈕自動升級成 warm，畫面只多「Resuming from snapshot」字樣。
4. **（B）可行性試做（spike，2–3 天，做不通就停在 A）**：VDS 上手寫 OCI bundle（一個資料夾放 config.json 與根檔案系統），直接 `runsc create/start` 不經 Docker；`--network=sandbox`（gVisor 自己的網路堆疊，跟著 checkpoint 一起存），手寫腳本建 netns + veth + NAT（這支腳本第 6 步做法第 3 項直接沿用）；pty daemon 在沙盒內聽 TCP（不用 `runsc exec -t`，主機端的檔案描述子存不進 checkpoint）。跑一輪 checkpoint → delete → create → restore → tmux attach。量 1／2／4 GB 的 checkpoint／restore 秒數與影像大小、Claude Code 閒置 5 分鐘平均 CPU、限速中 vs 解除限速的 checkpoint 時間差。同時確認三個前提：直接驅動 runsc、主機 cgroup v2（第 1 步裝機已檢查）、/workspace 是 bind mount。
5. **（B）Runner 換底層：Docker → runsc OCI bundle + 自建 netns**（1 週）：rootfs 用 `docker export` 映像檔解包成 bundle；runner 自己產 OCI config（User、PidsLimit、cgroup 路徑、bind mount、`linux.namespaces[network].path`）；exec 改 `runsc exec`；資源限制改直接寫 cgroup；create／destroy 呼叫試做的 netns／veth／NAT 腳本；runner 啟動時 `runsc list` 對照控制平面（做法第 7 項）。第 1 步的 docker-adapter 整層換成 runsc-adapter，API 形狀不變；第 5、6 步的磁碟與網路都接在這裡。做不通就停在 A，第 5、6 步走各自寫好的 Docker 退路。
6. **（B）Suspend／Resume adapter** `runner/internal/lifecycle/gvisor.go`：Suspend 先檢查剩餘空間 ≥ 記憶體上限 × 1.2（不夠留 Idle 記 `disk_full`）→ 先把 `cpu.max` 寫回 `max`（限速中 checkpoint 會拖到好幾分鐘）→ 關 bridge 連線 → `runsc checkpoint --image-path=/var/lib/sandbox/ckpt/<id>/<unix_ts> --compression=flate-best-speed` → 成功再 `runsc delete`，事件 `suspended{mode: warm, snapshot_gib}`。影像目錄 0700、不留暫存檔。Resume：建回 netns → `runsc create` → `runsc restore`，寫 `resumed{ms, mode: warm, runtime: gvisor}`。同一份 checkpoint 只 restore 一次，成功後保留 1 小時再刪。**保留期**：Suspend 影像與冷 Suspend 的 volume 都保留 30 天（`workspaces.retention_days` 可調），到期前 3 天在 Activity 與 email 提示，到期後影像刪除、volume 移到 trash（沿用第 5 步規則）並寫 `destroyed{reason: expired}`；詳情頁顯示「保留至 <日期>」。restore 失敗標 `Suspend(error)`、保留影像、清殘留。
7. **（B）Resume 路徑、冷開機、對帳、Lost**：三個觸發點（web 終端、CLI connect、API resume）都是 `/state {status:'Active'}`，控制平面轉打 runner。`POST /v1/sandboxes/{id}/cold-start`：清掉 snapshot_ref 用同一個 bundle 重開，/workspace 檔案都在，寫 `resumed{mode: cold}`。runner 每次啟動 `runsc list` 對照 control-plane 清單：容器不在、沒 checkpoint → `Lost`；有 checkpoint → Suspend；容器在就以 runner 為準。watchdog（唯一定義處）：控制平面連續 90 秒沒收到 runner 心跳 → 寫 `lost`（at＝最後一次通訊時間）；runner 那端失聯 90 秒後自動把 Active／Idle 沙盒做冷 Suspend，重連後回報實際狀態，控制平面再寫對應事件。畫面加 Suspend(error)／Lost 徽章與「Start fresh from workspace」按鈕；CLI `sandbox connect` 遇 Suspend 印「Resuming from snapshot… 3.2s」，新增 `sandbox start-fresh <id>`。
8. **（B）驗收腳本** `scripts/tiering-demo.sh` 與五個邊界：(a) checkpoint 失敗（disk_full 留 Idle）、(b) restore 失敗（`truncate` 弄壞影像 → Suspend(error)、Start fresh 可用）、(c) control-plane 短暫斷線（runner 失聯 90 秒後把 Active／Idle 沙盒冷 Suspend，重連後回報狀態；不做本機事件補送，時間戳一律由 Postgres 蓋）、(d) runner 重啟／容器消失（`runsc delete -f` 再 `systemctl restart runner`，30 秒內標 Lost）、(e) Agent busy 期間不暫停。README 補「暫停影像含記憶體內容，目前未加密」、保留期與秒數表。

**技術選型**

| 選擇 | 理由 |
|---|---|
| gVisor runsc 直接驅動 OCI bundle 做 checkpoint／restore | 一般 VPS 沒 /dev/kvm 也能 suspend；不經 Docker 是因為 containerd 管的容器背後 checkpoint／delete 會壞掉；之後 Firecracker 只換 adapter |
| cgroup v2 的 cpu.max 與 cpu.stat | Linux 內建，沙盒裡不用裝東西就能限速 Idle 與量 CPU |
| Claude Code hook（UserPromptSubmit／PreToolUse／Stop）與 Codex notify | 不改 Agent 程式碼就拿到「開始做」與「做完」，取代研究文的 SDK pause() |
| 沙盒內 pty daemon 聽 TCP、主機 bridge 經沙盒 IP 連 | 沙盒裡沒有主機端檔案描述子，checkpoint 才存得起來 |
| tmux + `status-interval 0` | session 跟 checkpoint 一起存一起回來 |
| 沿用第 2 步的 `workspaces` policy 欄位與 `sandbox_events` | 伺服器端單一時鐘、單一事件表，第 7 步直接讀；不另建表就不用改前端兩次 |
| 失聯時 runner 自動冷 Suspend、不做事件補送 | 時間戳永遠由 Postgres 蓋，跟第 7 步「Lost 段計 0、實體一定真的停」一致，程式最少 |
| A 段冷 Suspend、B 段升級成 warm | B 段做不通產品仍有 Suspend；第 7 步「Suspend 只收快照儲存費」在兩種模式都成立（冷的算 volume 保留） |
| Go table-driven 測試 | 狀態機是純函式，改規則不用開真沙盒 |

**預估**

1 人 × 5 週。A 段 1 週（第 1 週末就能 demo 自動 Idle 與冷 Suspend）；可行性試做半週；換底層 1 週（做法第 5 項，之前沒估到的隱藏工作）；adapter 1 週；resume／冷開機／對帳／保留期與畫面 1 週；驗收半週。最花時間的是把 runsc checkpoint／restore 接回 pty daemon 與 tmux 重連，還有失敗與重開後的清理。試做做不通就停在 A（4 週省下），不算延期。

**驗收**

1. `PATCH /v1/workspace {idle_after_s:60, suspend_after_s:120}` 回 200。
2. 建沙盒、寫 marker、瀏覽器開著不關、人離開：約 60–70 秒後 state 變 Idle，`cpu.max` 顯示 `<quota> 100000`，Activity 多一行「No keyboard input 1m · CPU 1% → Idle (auto)」。
3. 按一下 Enter：1 秒內有反應，10 秒內 Active，events 多一筆 reason=input。
4. `sandbox-agent done` → 30 秒內 Idle；`sandbox-agent busy; sleep 300; sandbox-agent done` → 5 分鐘內只會 Active 或 Idle、`hold` 顯示 agent_busy。
4a. （A）Idle 再放 120 秒 → Suspend，事件 `suspended{mode: cold}`，`docker ps` 沒有該容器；`sandbox connect` → 新 shell、marker 檔還在；`docker exec` 到 `:9001` 的 busy 請求被記為該沙盒。
5. （B）另建沙盒離開：約 60 秒 Idle、再 120 秒 Suspend，`runsc list` 找不到、ckpt 目錄權限 `drwx------`、事件 `suspended{mode: warm, snapshot_gib > 0}`；詳情頁顯示「保留至」30 天後。
6. （B）`sandbox connect` 印「Resuming from snapshot… N s」，回同一個 tmux 畫面，marker 還在；events 順序 active→idle→suspended→resumed，`resumed.resume_ms` 與 N 一致。
7. （B）`bash scripts/tiering-demo.sh --edge all` 五項 PASS；(b) 在 console 看到 Suspend(error) 與 Start fresh，按下後 marker 仍在；(c) 拔掉 WireGuard 2 分鐘，Active 沙盒在 VDS 上被冷 Suspend，接回後控制平面顯示 Suspend、事件表沒有補送的舊時間戳。
8. README 有秒數表、保留期與「影像未加密」說明。

**風險**

1. 前提是 runner 直接驅動 runsc、cgroup v2、/workspace bind mount、終端經沙盒內 TCP。第 1 步是 Docker + runtime=runsc，checkpoint 做不了；試做會發現，換底層已獨立估 1 週（做法第 5 項）；換不動就停在 A，第 5、6 步走 Docker 退路。
2. runsc restore 要求 checkpoint 與 restore 的 runsc 版本、CPU 一致：釘死版本，只在同一台恢復。
3. checkpoint 是整份記憶體落地：4 GB 可能幾十秒、磁碟要夠；限速中一律先解除。
4. Codex 與 Harness 沒有「開始做」的 hook，只靠 CPU：長任務可能被暫停，恢復後靠 Agent 重試。
5. 閒置誤判（等長時間下載）：Idle 是限速不是凍結，要動時 `throttled_usec` 拉回 Active。
6. N 分鐘粒度抓的是「任務做完／等人回覆」，不是每次 LLM 呼叫；行銷文案要對齊。
7. 對外 TCP 在 Suspend 期間會被斷：靠 Claude Code／Codex 自帶重試。
8. 暫停影像含記憶體內容（對話、程式碼、token），只靠 0700、restore 後 1 小時刪除與 30 天保留期，沒有加密。
9. hook 是使用者可改的設定檔：刪掉就退回鍵盤與 CPU；2 小時上限確保不會永遠 busy。第 6 步的防火牆若忘了放行 `:9001`，hook 會靜默失效——第 6 步 e2e 有一案專門驗。

**這一步先不做**

Firecracker snapshot／UFFD（第 8 步）；resume 後時鐘校正與 token 輪換（欄位先留 null）；跨主機恢復；從同一份 checkpoint 多次 restore 做 fork；計費金額（第 7 步）；API key 注入與出口白名單（第 6 步）；影像加密；Idle 時降記憶體；Codex／Harness 的「開始做」訊號；resume 後自動重送 LLM 請求；每沙盒個別 policy；失聯期間的事件補送（改為 runner 自動冷 Suspend）。

### 3.5 workspace-files：檔案與工作區（4 週，分 A／B 兩段）

**目標**

每個沙盒有一顆真的、會保留的磁碟（家目錄和 /workspace 都在上面）：能從 git repo 建立，瀏覽器和 CLI 都能上傳下載（含資料夾與大檔續傳），快照與 fork 帶著檔案和登入狀態走，Suspend 前可選擇把工作推到 git 分支。

**做完會看到**

1. **A 段（第 2 週末）**：建立表單填 Repository 後，終端真的看到 `Cloning into '/workspace'...`。Files 分頁改接真後端：列真實檔案、麵包屑進出子資料夾、Download 拿真檔（資料夾拿 .tar.gz）、顯示「已用 X / 10 GiB」，「每檔 10 MB」文案拿掉。Activity 按 Snapshot 1–3 秒出現快照，Snapshots 列表每筆標「保留至 <日期>」（預設 30 天，Usage 頁可調）；按 Fork，新沙盒 `ls /workspace` 一模一樣、兩邊改檔互不影響，原沙盒 `gh auth login` 過的登入狀態在 fork 裡還在。把 VDS 重開機，沙盒的檔案還在。建立表單的 4 vCPU 選項在 VDS 換大機後解鎖。
2. **B 段（第 4 週末）**：拖一個 500 MB 檔案到 Files 分頁看得到進度條；中途拔網路自動重試；重整頁面後把同一個檔再拖進來從中斷點接著跑；100% 後要等後端「匯入完成」才變綠。詳情頁多「Suspend 時 push 分支」開關，Suspend 後 GitHub 出現 `sandbox/<id>` 分支，第二、三次也會更新。CLI 新增 `sandbox cp ./big.bin sbx_abc:/workspace/big.bin`（Ctrl-C 再跑會續傳）、`sandbox cp ./dir sbx_abc:/workspace/dir`、`sandbox cp sbx_abc:/workspace/out .`、`sandbox fork`；`sandbox snapshot` 與 `sandbox claude --repo` 第 3 步已有，這步只是後面接真磁碟。

**做法**

1. **（A）每沙盒一顆 ext4 磁碟**：前置——VDS 資料碟第 1 步裝機時已格成 XFS 並開 reflink（複製檔案只記共用區塊，幾乎不占空間也不花時間）掛在 `/var/lib/sandbox`、核心 5.6+，這步只驗不重做；映像預裝 git、gh，注入 `SANDBOX_ID`。Runner 從這步起以 root 跑（只在 adapter 內呼叫 mount 這類特權操作，檔案服務另外降權，見做法第 3 項），在 create 時跑 `runner/volume.sh create <id> <size>`：`truncate -s 10G volumes/<id>.ext4 && mkfs.ext4 -q -m 0` → `mount -o loop`（把一個檔案當磁碟掛起來）→ `rmdir lost+found`（留著 git clone 會說目的地不是空的）→ 複製預設 dotfiles → `mkdir workspace` → `chown -R 1000:1000`。寫進 runsc 的 OCI spec 兩個 bind mount：`mnt/<id>` → `/home/agent`、`mnt/<id>/workspace` → `/workspace`；rootfs 維持暫存 overlay（apt 裝的東西不保留）；runsc 加 `--file-access-mounts=shared` 讓沙盒看得到主機端新寫進 volume 的檔。**若第 4 步停在 A（仍為 Docker）**：改 `docker run --mount type=bind,src=<mnt>/<id>,dst=/home/agent`，`daemon.json` 的 runsc runtimeArgs 加 `--file-access-mounts=shared`，其餘不變。可靠性：mount 可重複執行；runner 啟動時掃 `volumes/*.ext4` 對照控制平面重掛，無記錄的搬到 `orphans/`；create 失敗走同一支 destroy；destroy 是 `mv` 到 `trash/`，cron 7 天後真刪。空間守門（thin provisioning＝每顆先答應 10 GiB、實際用到才占）：create／fork／snapshot 前 `df` 剩餘 ≥ 一顆 volume 否則 507；cron 每小時低於 15% 寄 email；`config.yaml` 加 `volume_size_gib`、`max_sandboxes_per_host`。
2. **（A）從 git repo 建立**：沿用第 3 步的 `sbx-agent-start <agent> [repo]`（clone 在沙盒的 tmux 裡跑，之後的出口政策與憑證注入才一致），這步只加：/workspace 換成 volume 上的目錄、只接受 `https://`、timeout 10 分鐘、clone 輸出留在 tmux 畫面；雛形建立表單的 `Cloned … (demo)` 那行拿掉。只支援公開 repo。
3. **（A）檔案程式 sandbox-files**（Go 約 400 行，systemd `User=sandbox` uid 1000，只聽 127.0.0.1；root 只負責 mount）：`GET /files?path=`、`GET /files/download?path=`（資料夾用 `archive/tar` + gzip 串流）、`DELETE /files`、`POST /files/mkdir`、`GET /files/usage`（statfs）、`PUT /files/import`。路徑安全是安全邊界：所有 open／mkdir／unlink／rename 一律透過 Go 1.25 `os.Root`（底層 openat2 + RESOLVE_IN_ROOT，由核心保證解析不會跑出根目錄，連沙盒在兩步之間把資料夾換成 symlink 也擋）；Go 太舊改 securejoin。控制平面 proxy 到它並檢查沙盒屬於登入者。Suspend 期間：列表、下載、新增、建資料夾可以；刪除與覆寫回 409「請先 Resume」（runsc checkpoint 恢復時要求開著的檔還在）。瀏覽器 `filePanel()`／`readFiles()` 的 IndexedDB 換成呼叫 API，加麵包屑與「已用 X / 10 GiB」。
4. **（A）Snapshot 與 Fork**：`POST /sandboxes/{id}/snapshot`：空間守門 → `runsc pause` → `fsfreeze -f mnt/<id>` → `cp --reflink=always volumes/<id>.ext4 snapshots/<snap-id>.ext4`（10 GiB 約 1 秒）→ `fsfreeze -u` → `runsc resume`（第 4 步停在 A 時用 `docker pause/unpause`）。Fork：`cp --reflink=always` 快照當新 volume，走一般開機；家目錄在 volume 上所以 gh 登入、~/.claude 都在。**保留期**：`snapshots` 表加 `expires_at`（預設 30 天，`workspaces.retention_days` 可調，跟第 4 步的 Suspend 影像同一個欄位）；詳情頁 Snapshots 列表與 Activity 顯示「保留至 <日期>」；cron 每晚刪過期快照並寫 `sandbox_events{kind: destroyed, reason: expired}`。雛形 Snapshot／Fork 按鈕與終端 `sandbox snapshot` 改打 API，刪掉複製 IndexedDB 的程式；快照 log 改成「/workspace 與家目錄快照（不含記憶體）」。
5. **（B）大檔續傳上傳**：`tusd`（tus＝分段上傳、斷線後從中斷點續傳的開放協定，官方伺服器單一執行檔）跑在 VDS、暫存放同一顆 XFS 碟，控制平面反向代理 `/tus/`。token：`POST /sandboxes/{id}/upload-token` 拿 1 小時 JWT（帶簽章、可驗證沒被竄改的短字串），剩不到 60 秒就重拿。`pre-create` hook 用 `Upload-Length` 對剩餘空間提早回 507；`post-finish` hook 記 `importing` 並呼叫 `PUT /files/import`：串流寫到 `<mnt>/.sandbox-tmp/<upload-id>` 再 `root.Rename` 原子換入；`kind=tar` 逐筆走 `os.Root`，symlink 不建立、hardlink 拒絕、setuid/setgid 拿掉。`GET /sandboxes/{id}/uploads/{uploadId}` 給前端與 CLI 輪詢 done／failed + 原因。cron 每小時清 24 小時前的暫存。
6. **（B）瀏覽器上傳**：`upload()` 換 npm `tus-js-client`，`retryDelays: [0,1000,3000,5000]`、`storeFingerprintForResuming: true`（重整後把同一個檔再拖進來，用檔名＋大小＋修改時間認出來續傳）。每檔一條進度條；`onSuccess` 後輪詢到 done 才變綠。Suspend 時只鎖 Delete。
7. **（B）Suspend 時 push 分支 + CLI `sandbox cp`**：沙盒設定 `pushOnSuspend`，詳情頁加開關與「上次 push：時間／成功／失敗原因」。runner 的 suspend 入口在 pause 前 `runsc exec --user 1000:1000 <id> /usr/local/bin/sandbox-push-branch`：用臨時 index 做一個 commit、不動使用者分支，`git push --force origin "${c}:refs/heads/sandbox/${SANDBOX_ID}"`（一定要 `--force`，第二次起父提交都是 HEAD，否則 non-fast-forward 被拒）；timeout 60 秒；沒憑證記「失敗：no credentials」不再靜默。CLI `sandbox cp`（Go 300–400 行）：單檔走 tus，upload URL 存 `~/.sandbox/uploads.json`，Ctrl-C 重跑先 `HEAD` 拿 Upload-Offset 續傳；資料夾先 tar 到本機暫存再當單檔上傳；下載資料夾用 `archive/tar` 解到目的目錄，同一套規則。
8. **（B）快照備份與磁碟告警**：每晚 `rclone copy snapshots/ backup:sandbox-snapshots`（快照是 reflink 檔，先 `cp --sparse=always` 到暫存再傳，保留期跟 `expires_at` 一致）。沙盒 volume 本身明寫為**單機、不備份的已接受風險**（README 與定價頁揭露：「Snapshot 才有異地備份」）。做法第 1 項的 `df` 告警納入第 7 步做法第 7 項的同一支 mail 腳本。

**技術選型**

| 選擇 | 理由 |
|---|---|
| ext4 映像檔 + `mount -o loop` | 每沙盒一顆磁碟、容量上限免費送；之後 Firecracker 直接掛成 virtio-blk；第 4 步停在 A 時改 Docker bind mount，其餘不變 |
| 家目錄也放 volume | gh 憑證、~/.claude、shell 歷史跟著快照與 fork 走 |
| XFS reflink | 快照與 fork 一秒級，不用 LVM／ZFS；沒有 XFS 退回 `cp --sparse` |
| `runsc pause/resume` + `fsfreeze` + `--file-access-mounts=shared` | 現成的 gVisor 與 Linux 選項 |
| Go 1.25 `os.Root` | 「路徑不准跑出 volume」交給核心保證 |
| sandbox-files 獨立小程式、uid 1000 | root 只 mount，漏一個檢查也寫不到主機系統檔；runner 用什麼語言都不影響 |
| tusd + tus-js-client | 斷點續傳的成熟開放協定；跑在 VDS 讓暫存與 volume 同一顆碟 |
| git + 一支 bash script | clone 與 push 分支都用 git 本身 |
| 短效 JWT 上傳 token | 沿用控制平面的登入金鑰 |
| cron + `df` + 一封 email | 最無聊的空間告警 |

**預估**

1 人 × 4 週，A、B 各 2 週。B 段最花時間的是上傳鏈（tusd → hook → 匯入 → 狀態 → 瀏覽器續傳 → CLI cp），約 1.5 週；其次是路徑安全約 3 天；volume.sh 約 4 天（從 repo 建立與 snapshot 指令第 3 步已有，這步省下）。4 週偏緊；B 段落後就先把 push 分支與快照備份挪到下一步，續傳上傳優先。

**驗收**

1. A1：`sandbox claude --repo https://github.com/octocat/Hello-World` 看到 Cloning；`sandbox exec sbx_xxx -- ls /workspace`（第 3 步的 CLI 子指令）看到 README；/workspace 與 /home/agent 擁有者都是 uid 1000、沒有 lost+found。
2. A2：`GET …/files?path=/` 回含 README；`path=../../etc` → 400；沙盒內把 /workspace/a 換成指向 / 的 symlink，`path=a/etc` → 400。
3. A3：`gh auth login` 後 `sandbox snapshot` 1–3 秒回 snap_yyy，詳情頁 Snapshots 列表顯示「保留至」30 天後；`sandbox fork snap_yyy` 回新 id；原沙盒 rm README，fork 裡 README 還在、`gh auth status` 仍登入；把 `expires_at` 改成昨天，跑一次夜間 cron → 快照消失、Activity 有 `expired`。
4. A4：VDS `sudo reboot` 後 `ls /workspace` README 還在、Files 分頁不是空的。
5. B1：`dd … count=500` 做 big.bin，`sandbox cp` 到 40% Ctrl-C 再跑從 40% 接著；下載回來 `cmp` 無輸出；Files 分頁「已用 0.5 / 10 GiB」。
6. B2：瀏覽器拖 big.bin 到一半重整再拖同檔 → 從中斷點繼續；100% 後短暫「匯入中」再變綠。
7. B3：資料夾 `sandbox cp d …` 後 `cat /workspace/d/sub/x.txt` 印 hi；11 GB 的 huge.bin → 立刻 507。
8. B4：Suspend 後 DELETE 檔案 → 409；新增檔案成功。
9. B5：開啟 push 開關，改 README 後 suspend → GitHub 出現 `sandbox/sbx_xxx` 分支、main 不動、詳情頁「上次 push：成功」；resume 再改再 suspend → 第二次也成功。

**風險**

1. 主機端直接讀寫 volume 在 Firecracker 階段行不通（VM 跑著時同一顆碟不能同時在主機掛）：屆時 sandbox-files 搬進 guest 經 vsock 呼叫；現在先集中在一支程式。
2. Suspend 期間改到 Agent 開著的檔可能讓 restore 失敗：先用 409 擋刪除與覆寫，並做一次實測。
3. loop mount 需要 root，loop device 數量有限：100 個沙盒要先壓測。
4. XFS reflink 要自己格式化資料碟；只有 ext4 系統碟就退回 `cp --sparse`。
5. thin provisioning 空間守門是粗的：告警門檻要照實際用量調。
6. tusd 暫存與匯入是兩段，中間掛掉會留孤兒：hook 要能重跑，cron 清理。
7. push `--force` 只保留最新一份自動存檔，README 要寫明。
8. clone 大 repo 塞爆 10 GiB 或跑很久：先靠 timeout 與空間錯誤擋。
9. 上千個小檔一檔一個 tus upload 很慢：先限 2000 個。
10. tar 解壓與 os.Root 是安全邊界，要有測試覆蓋 symlink、絕對路徑、`..`、競態。
11. 反向代理要放行大 body 與長連線（`client_max_body_size 0`、`proxy_request_buffering off`）。

**這一步先不做**

記憶體快照與執行中狀態的 fork（第 4、8 步）；私有 repo 憑證與 vault 注入（第 6 步）；自動存檔分支保留歷史；volume 本身的異地備份（已接受風險，只備份快照）、跨主機搬遷；垃圾桶 restore API；磁碟計費與 xfs_quota；檔案版本歷史、線上編輯器；瀏覽器每檔暫停按鈕；Suspend 期間允許刪除覆寫；rootfs 變更跟著快照走；clone `--depth` 選項與 volume 動態擴充；NFS、9p、virtio-fs。

### 3.6 secrets-network：祕密與網路（4 週，分 A／B 兩段）

**目標**

Agent 在沙盒裡能正常呼叫 Anthropic／GitHub（Codex 盡力），但沙盒內找不到任何真的 API key；真 key 也不會以明文離開 control plane；對外連線預設全擋、只放白名單，沒走 proxy 的連線立刻失敗而不是卡住；每一筆連線都有紀錄。

**做完會看到**

1. **A 段（第 2 週末）**：`sandbox secrets set ANTHROPIC_API_KEY` 貼上真 key，畫面只印末四碼。`sandbox claude` 進沙盒，`env | grep -i key` 只看到 `ANTHROPIC_API_KEY=sandbox-managed`，但 `claude -p "say hi"` 照常回答。`curl https://example.com` 一秒內回 403；沙盒裡裝套件（pip、apt）照常能用；用側錄工具（tcpdump）抓伺服器之間的流量，找不到 Anthropic key 的開頭 `sk-ant-`。
2. **B 段（第 4 週末）**：雛形詳情頁多「Network」分頁，列出 api.anthropic.com 綠色 allow、example.com 紅色 deny、pypi.org、archive.ubuntu.com。Usage 頁多「Secrets」與「Egress allowlist」兩個區塊；加 example.com 後等 10 秒再 curl 就通。`sandbox egress log <name>` 在自己電腦看同一份紀錄。`bash egressd/e2e_test.sh` 全部 PASS。M3 之前請一位外部工程師花 1 天審過防火牆反偽造與檔案路徑處理，結論附在 PR。

**做法**

1. **（A）加密通道與祕密庫**：
   - 加密通道：沿用第 3 步的 WireGuard（VPS 10.8.0.1、VDS 10.8.0.2）。control plane 的 `/internal/*` 只綁 `10.8.0.1:8081`，`X-Internal-Token` 用 `ConstantTimeCompare` 比對。
   - 祕密庫：Postgres 新表 `workspace_secrets`，name 只准 ANTHROPIC_API_KEY（header `x-api-key`）、OPENAI_API_KEY（`Authorization: Bearer`）、GITHUB_TOKEN（`Authorization: Basic`）；用 libsodium secretbox 加密，主金鑰 `SECRETS_MASTER_KEY` 由 systemd `LoadCredential=` 餵入；產生時同時存到備份 bucket 的另一個受限前綴與創辦人的密碼管理器。API `PUT/GET/DELETE /v1/workspaces/:ws/secrets/:name`（GET 永遠不回值）。內部端點 `GET /internal/resolve?ip=` 回沙盒身分、白名單、secrets；status 不是 running 就不回 secrets。
   - 沙盒 IP 分配：由 control plane 遞增分配（從 10.77.0.2 往上，用完繞回），destroy 才釋放，suspend／resume 沿用——讓同一個 IP 很久才再用到，避免 proxy 快取把舊沙盒的 key 給新沙盒。
   - CLI：`sandbox secrets set|ls|rm`（值從隱藏輸入或 stdin 讀，不接受命令列參數）。
2. **（A）egressd 出口 proxy**（Go 標準庫，監聽 `10.77.0.1:3128`，管理端點 `127.0.0.1:3129`）：(a) `CONNECT host:443` 查白名單，允許就 hijack 雙向轉送，否則 403；只准 443。(b) 純 http 的 proxy 請求（apt 走這種）套同一份白名單，只准 80。(c) 換 key 路徑：`/anthropic/*` → api.anthropic.com 換 `x-api-key`；`/openai/*` 換 Bearer；`/github/*` 有 token 才加 Basic、沒 token 照轉（公開 repo 才能 clone）；三條都 `req.Host = target.Host` 並先刪掉沙盒送來的 header；`FlushInterval=-1` 讓串流回應不被緩衝。身分辨識用來源 IP 打 `/internal/resolve`，結果只放記憶體：每 10 秒重驗、control plane 連不上最多沿用 5 分鐘、`POST 127.0.0.1:3129/flush?ip=` 立刻清掉。每筆請求 `log/slog` 一行 JSON，批次 `POST /internal/egress-events`；不記內容。
3. **（A）沙盒網路**：沿用第 4 步試做建的 netns／veth 腳本（host 端命名 `sbx-<id>`，runsc 透過 OCI config 的 `linux.namespaces[network].path` 使用），這步只加 IP 分配與 nftables。host 端 veth 接到 bridge `sbx0`，子網 `10.77.0.0/16`，閘道 10.77.0.1 就是 proxy。netns 內關 IPv6。nftables `table inet`：`set sbx_ok { type ifname . ipv4_addr }` 反偽造 → 只准到 10.77.0.1:3128（proxy）與 10.77.0.1:9001（第 4 步的 `sandbox-agent` hook 端點）→ 其餘 `reject`（tcp 回 reset，讓 curl／pip 立刻報錯，`drop` 會等 30 秒到 2 分鐘）；forward chain 全拒（沙盒之間不通）。runner create／resume 先拿 IP 再 `nft add element`，失敗就不啟動；suspend／destroy 時 `nft delete element` + flush + 通知 control plane，任一失敗直接 destroy。**若第 4 步停在 A（仍為 Docker）**：沙盒留在 Docker user-defined bridge，veth 名稱由 runner 從 `docker inspect` 取得，同一份 nftables 規則套在那組介面上；IP 改由 runner 在 `docker run --ip` 指定。
4. **（A）Runner 注入環境與 rootfs 預設**：OCI `process.env` 帶 `HTTP_PROXY`／`HTTPS_PROXY=http://10.77.0.1:3128`、`NO_PROXY`、`ANTHROPIC_BASE_URL=http://10.77.0.1:3128/anthropic`、`ANTHROPIC_API_KEY=sandbox-managed`、`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`、`NODE_USE_ENV_PROXY=1`。rootfs 預放 `/etc/gitconfig`（`insteadOf` 把 github.com 改走 proxy）、`/home/agent/.claude.json`（hasCompletedOnboarding、customApiKeyResponses.approved 放 sandbox-managed 的對應值；開工第一天先驗格式，不行改 `apiKeyHelper`）、`/etc/apt/apt.conf.d/99proxy`。鎖定 Claude Code 版本。Codex（盡力）：不設 OPENAI_API_KEY，config.toml 加 `model_providers.sandbox` 指向 proxy。
5. **（B）連線紀錄與白名單進畫面與 CLI**：表 `egress_events`、`workspace_egress_allow`（只做完整比對；預設 archive.ubuntu.com、security.ubuntu.com、ports.ubuntu.com、registry.npmjs.org、pypi.org、files.pythonhosted.org、objects.githubusercontent.com、codeload.github.com）。API `GET /v1/sandboxes/:id/egress`、`PUT/DELETE /v1/workspaces/:ws/egress/:host`。雛形 `detail()` 在 terminal／files／activity 旁加 `network` 分頁（時間｜目的地｜類型｜狀態碼｜結果，每 3 秒輪詢）；`usage()` 加 Secrets（名稱、末四碼、Rotate／Remove）與 Egress allowlist 區塊，提示「最多 10 秒後生效」。CLI `sandbox egress log|allow|rm|ls`。
6. **（B）紀錄去識別、外部審視與 e2e**：沒有終端錄影（整份計劃不做），去識別只針對 `egress_events` 的 path 與 API／Caddy 日誌：規則放 `secret_patterns.{go,js}`（`sk-ant-`、`sk-proj-`、`ghp_`、`github_pat_`、`gho_`），寫入前 `scrub()`，串流日誌把上一段最後 200 bytes 併進來比對，避免 key 被切成兩半漏抓。M3 前找一位外部工程師花 1 天審 nftables 反偽造與 os.Root 路徑處理（算在這步估時內）。`egressd/e2e_test.sh` 九案：偽造 IP 被擋、example.com 403 且不走 proxy 1 秒內失敗、pip／apt 成功、有 token clone 私有 repo 且 env 看不到 token、無 token clone 公開 repo、destroy 後同 IP 給另一租戶必須 401、把 key 當 URL path 打 proxy 後 egress log grep 不到、tcpdump 抓不到 `sk-ant-`、白名單全擋下 `sandbox-agent busy` 仍能送達 `:9001`。

**技術選型**

| 選擇 | 理由 |
|---|---|
| Go 標準庫寫 egressd | CONNECT、純 http 轉送、換 header 各 20–50 行；不用 Envoy（太重）、LiteLLM（不處理 GitHub 與 apt） |
| WireGuard | 內部端點根本不在公網上；之後其他內部呼叫共用 |
| nftables `table inet` + `ifname . ipv4_addr` set + `reject` | 一次管 IPv4／IPv6，被擋的工具立刻失敗；第 4 步的 veth、Docker 退路的 veth、之後 Firecracker 的 TAP 同一套規則 |
| libsodium secretbox + Postgres 加密欄位 | 這就是我們的祕密庫；不裝 Vault／OpenBao（unseal、HA、升級對 1–2 人太重）；研究文的「vault／proxy」重點是明文不進沙盒，由 proxy 達成 |
| systemd（LoadCredential、wg-quick@） | 保管內部 token 與主金鑰 |
| Claude Code `ANTHROPIC_BASE_URL` + 預填 `.claude.json`、Codex `model_providers`、git `insteadOf`、apt Proxy | 官方支援的改址方式，不用偽造 TLS 憑證 |

**預估**

1 人 × 4 週，A、B 各 2 週。最花時間的是沙盒網路（約 1 週）：IP 分配、nftables 反偽造、runner 三個時點的順序，做錯就是跨租戶用到別人的 key（netns／veth 腳本第 4 步已有，省下約 2 天，剛好換成外部審視 1 天）。其次是逐一驗證 Claude Code、git、pip、npm、apt 走 proxy。Codex 超過半天就先放。

**驗收**

1. `sandbox secrets set ANTHROPIC_API_KEY` → 印 `saved (****k1Ab)`。
2. 沙盒內 `env | grep -Ei 'anthropic|openai|github'` 只有 sandbox-managed 與 BASE_URL，沒有 `sk-ant-`。
3. `claude -p "say hi"` 正常回覆。
4. `time curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://example.com` → 403 且 1 秒內；`env -u HTTPS_PROXY -u HTTP_PROXY curl …` 1 秒內失敗不卡逾時。
5. `pip download requests` 與 `sudo apt-get update` 成功。
6. VDS `tcpdump -i eth0 -A -c 500 host <VPS IP> | grep -c 'sk-ant-'` 同時跑 `claude -p` → 0。
7. （B）`sandbox egress log sec-test` 至少有 anthropic allow、example.com deny、pypi allow、archive.ubuntu.com allow；Network 分頁同樣幾筆，deny 紅色。
8. （B）`sandbox egress allow example.com` 後等 10 秒 → 200；Usage 頁刪掉後再等 10 秒 → 403。
9. （B）`SANDBOX_TEST=1 bash egressd/e2e_test.sh` 九案 PASS（含 egress log 與 API 日誌 grep 不到 `sk-ant-`、hook 打得到 `:9001`）；外部審視的結論附在 PR。

**風險**

1. 身分靠來源 IP：靠 nftables 反偽造、IP 遞增分配、suspend／destroy 時 flush 三層；漏任何一層都可能跨租戶。
2. WireGuard 斷掉時 egressd 最多沿用 5 分鐘快取，之後全部拒絕，所有 Agent 都停；告警在第 7 步做法第 7 項（沿用快取超過 5 分鐘寄一封）。
3. Codex 對自訂 base_url 支援不穩：以 Claude 為準，最後手段才是 MITM 憑證（自己簽憑證去解開 HTTPS 的中間人做法，在 defer）。
4. `~/.claude.json` 格式隨版本變：鎖版本，備案 apiKeyHelper。
5. 不吃 HTTP_PROXY 的工具會立刻失敗但 Network 分頁看不到：寫進文件當已知限制。
6. 沙盒到 proxy 之間是明文 HTTP，走同一台主機 bridge；先接受。
7. 主金鑰遺失＝所有祕密作廢：產生時就存到 bucket 受限前綴與創辦人密碼管理器（做法第 1 項）；真丟了使用者重貼即可。
8. egressd 是單點：無狀態、systemd 自動重啟。
9. Claude Code 可能連我們沒列的端點：已關非必要流量；Network 分頁出現新 deny 再決定。

**這一步先不做**

Vault／OpenBao、KMS；MITM TLS 檢查；短效祕密租約與輪換；Codex 驗收、`gh` CLI、Claude 訂閱 OAuth；`egress log --follow`；白名單萬用字元；control plane 主動通知 egressd；保留含 ANSI 的原始逐字稿；記錄請求內容、解析 token 用量（若第 5 節決定 6 改成平台代付，在 egressd 這裡加）；顯示 nftables 拒絕的連線；DNS 白名單或透明代理；inbound／preview URL；第二台 VDS；audit log 長期保存；終端錄影與 transcript。

### 3.7 metering-billing：計量與收費（5 週，分 A／B 兩段）

**目標**

把沙盒每一次狀態切換記成「伺服器蓋時間戳」的事件，用同一條 SQL 計算路徑算出 vCPU-秒與 GiB-秒，讓雛形 Usage 頁、額度上限、推 Stripe 三處看到的是同一份數字；單價以 Stripe 為唯一真相；帳本每晚備份、每晚跟 Stripe 對帳，多算會抵、少算會補。

**做完會看到**

1. **A 段（第 2 週末，不需要 Stripe）**：Usage 頁不再是瀏覽器自己累加的模擬數字，而是 `GET /v1/usage` 的真實資料：每個沙盒各狀態累計秒數、本期金額、總額，每 15 秒更新，關掉分頁再開數字照樣在走。定價區塊從「三段各一個 $/hr」改成四個維度（vCPU-hr、記憶體 GiB-hr、磁碟 GiB-hr、快照 GiB-hr）的單價，每段狀態標明「這段收哪幾項」（Idle 只收記憶體＋磁碟、Suspend 只收快照，且只收保留期內），示意值掛「示意費率」標籤；Sandboxes 頁 stats 三張卡片的「$/hr 示意起價」改成各狀態「收哪幾項」的一句話，不放單價。頁面頂端多「本期已花／上限」進度條，可直接改上限；80% 黃色橫幅，超過紅色橫幅且 Launch／Resume 變灰。終端 `sandbox usage` 印同一份表格。
2. **B 段（第 4 週末）**：用 Stripe Checkout 綁測試卡後，Stripe 測試模式儀表板的 upcoming invoice 有四個 line item（發票上的一行項目），數量（秒）跟 Usage 頁一致。`sandboxd billing reconcile --day 昨天` 印一張全部 OK 的核對表（含「昨晚備份在 24 小時內」）；用 Stripe CLI 多推一筆用量再跑會亮 DIFF，加 `--repair` 後 Stripe 客戶餘額出現負數抵扣、核對表回到全 OK。
3. **第 5 週（最小告警與正式收費）**：把 API 停掉、或讓昨晚備份失敗，創辦人信箱一小時內收到一封 email；VDS 的 runner 失聯 90 秒也會收到。Stripe 切成正式模式的清單走完：sync-prices 沒有任何 placeholder、正式費率由創辦人在 Stripe 設好、用真卡綁定出第一張真發票。

**做法**

1. **事件表**：沿用第 2 步定案的 `sandbox_events`（append-only、`at default clock_timestamp()`、`idem_key unique`），這步不建表、不改欄位，只確認每種 kind 都填齊 vcpu、mem_gib、disk_gib（第 5 步的配給量）、snapshot_gib（suspended 時填 runner 回報的快照大小；冷 Suspend 填 volume 已用量）。時間戳只由 VPS 的 Postgres 蓋，API 請求結構裡沒有 `at`，runner 那台的時鐘準不準都無所謂（第 4 步已改成失聯時 runner 自動冷 Suspend，沒有補送事件）。`RecordEvent(tx, …)` 必須跟 `update sandboxes set status` 同一筆交易；先查 idem_key、狀態相同就跳過、再 insert；BEFORE INSERT trigger 當最後防線。Lost 與 watchdog 的定義在第 4 步做法第 7 項，這步只規定：Lost 段四個維度都算 0，runner 重連後依回報的實際狀態重新計費。
2. **一條計算路徑**：view `sandbox_intervals` 用 window function（讓每一列看得到「下一列」的 SQL 寫法）`lead(at)` 把事件配成區間；SQL 函式 `usage_units(workspace_id, from, to)` 回每沙盒、每狀態的整數秒：active 算 vcpu／mem／disk，idle 的 vcpu 固定 0、只算 mem 與 disk，suspended 只算 snapshot 且只算到保留期（`expires_at`）為止，過期刪除後歸 0，lost 全 0。Usage 頁、額度、推 Stripe 三處都呼叫它，沒有小時匯總表要跟自己對帳。費率快取表 `price_book`（四列，`unit_amount_decimal` 是每單位-秒幾分錢，`is_placeholder`，`stripe_price_id`）：里程碑 A 手動塞雛形示意值換算、標 placeholder；B 起由 `sandboxd billing sync-prices` 從 Stripe 拉回覆蓋。金額＝每維度 `units × 單價` 各自四捨五入到分再加總。測試對著 `docker run postgres:16` 跑表格式案例（跨整點、resize、重送、lost 重連、跨月）。
3. **Usage API 與畫面**：`GET /v1/usage?from=&to=` 回 period、rates、每沙盒 seconds／units／amount_cents、total_cents、spend_limit_cents、warn_80、blocked；`GET /v1/sandboxes/:id/usage` 回區間清單。`src.js` 的 `usage()`、`cost(b)` 改吃 API（第 2 步已刪掉本機累加，這裡只換資料形狀）；5 秒 interval 改 15 秒重抓。pricing-grid 改四維度並標「這段收哪幾項」；stats 卡片的 $/hr 改成一句話；競品比較表「我們」那列改用四個單價套「2 vCPU / 4 GiB / 20 GiB，Active 20 分 + Idle 40 分」算，不再用 `rates.Active/3 + rates.Idle*2/3`。CLI `sandbox usage [--sandbox id] [--period 2026-09]`。
4. **額度上限**：`workspaces` 加 `spend_limit_cents`、`billing_blocked`；`PATCH /v1/workspace`。`sandboxd billing enforce` 由 systemd timer 每 5 分鐘跑：用自家帳本算已花，≥ 100% 對該工作區所有 Active／Idle 沙盒 suspend（source=billing）並設 blocked，之後建立與 resume 回 402；上限調高或新一期自動解除。80% 只做橫幅與 CLI 警告，不寄信。橫幅講清楚「已暫停的沙盒仍會產生快照儲存費」。
5. **Stripe 出帳**：
   - 先驗一次：花 30 分鐘在測試模式建 1 個 Billing Meter + 1 個 Price（`unit_amount_decimal`）、推 value=1800 看發票怎麼顯示，確認了才建正式四個。
   - Meter 與 Price：單位一律整數秒；4 個 Meter（vcpu_seconds／mem_gib_seconds／disk_gib_seconds／snapshot_gib_seconds）、1 個 Product 掛 4 個 metered Price，`metadata.dimension`、示意值標 `metadata.placeholder=true`。`sync-prices` 從 Stripe 拉回 price_book；live key 下任一 placeholder 就拒絕 exit 1。
   - 綁卡：`POST /v1/billing/checkout` 建 Checkout session（$0 底價、`billing_cycle_anchor` 下個月 1 日）。
   - 每小時推送：`meter_pushes` 出貨紀錄表（kind: push／adj／external／credit）。`sandboxd billing push` 每小時 :05 跑：每個沒推過的小時呼叫 `usage_units` 按維度加總 `POST /v1/billing/meter_events`，`identifier = "{ws}:{hour}:{dim}"`，只推沒推過的小時、不重推不改值。
   - Webhook：`POST /webhooks/stripe` 用 SDK `ConstructEvent` 驗簽（驗不過 400），只處理 invoice.paid、invoice.payment_failed、customer.subscription.updated；本機用 `stripe listen`／`stripe trigger` 測。發票、稅、催款全交給 Stripe。
6. **備份與對帳**：Postgres 備份沿用第 2 步的 cron + `pg_dump | gzip` + rclone（保留 30 天），這步不另建一套，只加 reconcile 的新鮮度檢查與失敗告警（做法第 7 項）。`sandboxd billing reconcile --day … [--repair]` 每晚 03:30（在備份之後）：(1) 不變量（區間不重疊不留空、各狀態秒數加總＝生命週期、suspended 的 snapshot_gib > 0、idle 的 vcpu 全 0）；(2) 逐小時重算跟 meter_pushes 淨值比，MISSING／DIFF；(3) 跟 Stripe `event_summaries` 比，整數直接相等；Stripe 多出來的記 external；(4) 備份新鮮度；(5) 週期第一天檢查上一期最後一小時在定版前推完。`--repair`：MISSING 補推；DIFF 為正推 adj event；為負走 `customer balance_transactions` 負數抵扣（Stripe 不能撤回也不能推負數）。原始事件永久保留。
7. **最小告警**（半週，M3 之內）：一支 `infra/bin/alert-mail.sh`（msmtp 或 API 寄到創辦人信箱），所有東西都經它寄。(a) 外部 uptime 服務（免費方案即可）每分鐘打 `https://console.<網域>/healthz`，healthz 順便回 runner 與 egressd 最後心跳時間，超過 90 秒就回 503 讓 uptime 服務發信。(b) 所有 systemd timer 與 cron（第 2 步的 backup、reconcile、push、enforce、第 5 步的快照備份與過期清理）加 `OnFailure=status-email@%n` 或 cron 包 `|| alert-mail.sh`。(c) runner 對 control plane 心跳超過 90 秒、egressd 沿用快取超過 5 分鐘各寄一封（同一事件一小時內不重寄）。(d) 第 5 步的 `df` 低於 15% 告警改走同一支腳本。
8. **正式收費清單**（約 3 天，M3.5）：Stripe live 切換清單寫成 `docs/runbook/stripe-live.md`：`sync-prices` 在 live key 下無 placeholder、webhook secret 換成 live、正式費率由創辦人在 Stripe 設定並跑一次 reconcile、Checkout 用真卡走一遍、定價頁與 README 拿掉「示意費率」標籤。這項只在創辦人決定費率後執行。

| 選擇 | 理由 |
|---|---|
| Postgres 16 + SQL view + 一個 `language sql` 函式 | 事件→區間→四維度只有一條計算路徑，psql 就能查、能重算；不引進 Kafka、時序資料庫、小時匯總表 |
| Stripe Billing Meters + metered subscription，整數秒 + `unit_amount_decimal` | 收卡、發票、稅、催款全外包；identifier 天生防重複；整數對帳不用容差；單價真相在 Stripe |
| Stripe customer balance transactions | 多算時的抵扣走 Stripe 內建客戶餘額，不自己出 credit note |
| Stripe CLI + test clock | 本機測 webhook，跨月定版實測一次 |
| systemd timer | push、enforce、reconcile 都是同一支 `sandboxd` 的子指令，失敗統一 `OnFailure` 寄信 |
| 沿用第 2 步的 cron + pg_dump + rclone | 全計劃只有一套備份工具；30 天保留與新鮮度檢查在這步補 |
| 外部 uptime 打 healthz + 一支 mail 腳本 | 最無聊的告警；不裝 Prometheus／Grafana |

**預估**

1 人 × 5 週（A、B 各 2 週，第 5 週告警半週 + 正式收費清單約 3 天）。最花時間的是 `usage_units` 的邊界（跨整點、跨月、resize、lost 重連、保留期到期）約 1 週，以及 reconcile 五項檢查加 `--repair` 兩個方向約 1 週；Stripe 接線約 1 週；Usage 頁、CLI、額度約 4 天。正式費率的數字仍由創辦人決定，第 5 週只做切換清單。趕不上先砍 `--repair` 的負數抵扣（第一個月用 Stripe Dashboard 手動調）。

**驗收**

1. A：`sandbox claude --name bill-test` → sleep 120 → suspend → sleep 60 → connect → sleep 60 → destroy → `reconcile --day today --sandbox bill-test` 印三段區間 Active 120s、Suspend 60s、Active 60s（±1 秒），加總＝240s，不變量全 OK。
2. 同一筆 runner 事件用同一個 idem_key 再送，`count(*)` 不變。
3. Usage 頁三段秒數跟上面一致；關掉分頁 5 分鐘再開秒數仍在增加；`sandbox usage` 數字相同。
4. idle 門檻改 1 分鐘，`GET /v1/sandboxes/:id/usage` 的 Idle 段 vcpu_sec = 0、mem_gib_sec > 0。
5. `PATCH /v1/workspace {"spend_limit_cents":1}` → 5 分鐘內全部 Suspend、`sandbox claude` 回 402、紅色橫幅；改回 null 解除。
6. VDS `systemctl stop sandbox-runner` 2 分鐘再啟動 → 事件流出現 lost 與重連後的狀態，Lost 段四維度都 0。
7. B：`sync-prices` 印四個單價標 placeholder；`push` 印 pushed N 再跑印 0；`reconcile` 全 OK；`stripe billing meter_events create … --payload value=100` 後 reconcile 亮 DIFF −100 exit 1；`--repair` 變「已抵」；再跑全 OK。
8. Stripe 儀表板 upcoming invoice 四個 line item，數量等於 `GET /v1/usage?to=上一個整點` 的 units；客戶餘額有負數交易。
9. `stripe trigger invoice.payment_failed` → billing_status 變 past_due；錯的 secret 打 webhook 回 400；test clock 撥到週期結束後 2 小時，最後一小時在這一期。
10. 備份還原：`rclone ls backup:sandbox-backups` 有今天 dump；灌到 `sandboxd_restore` 後 reconcile 全 OK。
11. 告警：`systemctl stop sandbox-api` → 5 分鐘內收到 uptime 信；把 backup cron 改成 `false` 跑一次 → 收到失敗信；VDS `systemctl stop sandbox-runner` 2 分鐘 → 收到心跳逾時信；同一事件一小時內只有一封。
12. 正式收費：`STRIPE_KEY=sk_live_… sandboxd billing sync-prices` 在有 placeholder 時 exit 1；runbook 走完後 Stripe live 儀表板有一張真發票。

**風險**

1. Idle 不收 vCPU 的前提是 runner 真的限縮 CPU（第 4 步的 cpu.max），否則等於貼錢。
2. Lost 期間刻意少算，實體一定要真的停：第 4 步已規定 runner 失聯 90 秒自動冷 Suspend；心跳 30 秒、逾時 90 秒是最大漏算範圍。
3. runner 沒回報快照大小時 Suspend 等於免費：reconcile 不變量會抓出來。
4. Stripe identifier 只在 24 小時內去重、timestamp 只能回填 35 天：超過只能人工。
5. 負數抵扣用我方快取單價算，改費率前先跑一次 reconcile。
6. 我方「本期」跟 Stripe 週期不對齊：一律從 subscription item 讀回。
7. 佔位費率沒換掉就切正式：靠 `metadata.placeholder` 擋，sync-prices 每次印四個單價。
8. 單台 Postgres 每晚一次備份，最壞丟一天事件；Stripe 有按小時加總，發票不會丟。
9. 同一交易內 `now()` 固定：一律 `clock_timestamp()`，排序 (at, id)。
10. 告警只寄 email、只寄給創辦人：信箱沒人看就等於沒告警；先接受，之後再接 Slack 或 pager。

**這一步先不做**

80% 寄信；預付點數、儲值、免費額度、優惠券；費率歷史與每工作區不同單價；多幣別與稅；每秒即時推 Stripe；push 自動修正差額；網路流量、物件儲存、LLM token 計費（BYOK 之下不需要，見第 5 節決定 6）；自家帳務後台；團隊席位與成本分攤；WAL 連續備份；Firecracker 快照大小最佳化；時序資料庫或訊息佇列；Prometheus／Grafana 這類監控平台；決定正式費率數字（創辦人在 Stripe 設定）。

### 3.8 firecracker-baremetal：Firecracker 與裸機（A 段 4 週 + B 段 3 週）

**目標**

先用 gVisor 版的數字確認值得做，再在一台 EPYC／Xeon 裸機上用 Firecracker 跑沙盒：A 段拿到 VM 等級隔離（Suspend 先用冷開機恢復），B 段做記憶體快照恢復（目標約 1 秒回到同一個終端畫面）；上層 API、CLI、雛形畫面不改，只靠工作區層級的 `runtime` 開關切換與回退。

**做完會看到**

1. **A 段（VM 隔離，4 週）**：閘門（做法第 1 項）做完，雛形 Usage 頁多一行「runtime: gvisor · resume p50 / p95（冷恢復）」，連到 `docs/adr/firecracker.md` 的 go／no-go 結論（ADR＝架構決策紀錄，一頁說明為什麼這樣選）。workspace 打開 `runtime=firecracker` 後，`sandbox claude` 拿到一台跑在裸機 VM 裡的沙盒，詳情頁右上角標籤改成「firecracker · ax-01」。`sandbox suspend` 再 `sandbox connect`，幾秒後冷開機回來，/workspace 的檔案還在，Activity 顯示「Resumed in 3.1 s · firecracker · cold boot」。Snapshot／Fork 先做磁碟快照。
2. **B 段（記憶體快照，3 週）**：Suspend 後 `sandbox connect` 約 1 秒回到同一個 tmux 畫面，Activity 多「Resumed in 0.9 s · firecracker」（runner 量到的毫秒數）。Snapshot／Fork 變成真正的記憶體快照：Fork 出來的沙盒接著原本的畫面繼續跑、token 是新的、時鐘是對的。ADR 一頁寫清楚什麼情況才值得派到 Firecracker、開關一關就回 gVisor、快照與升級規則。

**做法**

1. **閘門（不租機、不裝東西）**：從第 7 步的 `resumed{ms, mode, runtime}` 事件拉最近一週每日 resume 次數與 p50／p95；沒有正式使用者就用 `infra/bench/resume.sh <gvisor_sbx_id> 20 --cold` 量（腳本先在 gVisor 版寫好，之後共用；`--cold` 每次先 drop_caches，量的是「冷恢復」）。只有其中一項成立才 go：gVisor checkpoint restore（drop_caches 後）p95 > 5 秒、慢到影響自動降級體驗，或有客戶明確要求 VM 等級隔離。先算錢：EPYC／Xeon 裸機每月約 €200–250。結論寫成 ADR 第一節；no-go 就整步停。
2. **裸機開通**：租 Hetzner AX162（AMD EPYC 9454P）或 Hetzner Dell PowerEdge Xeon 機種；不租 AX41／AX52／AX102 這些 Ryzen 桌機 CPU（不在 Firecracker 官方支援清單，快照相容性沒人替你測）；第二台一定同型號。installimage 裝 Ubuntu 24.04，/srv/fc 獨立格成 XFS reflink=1，整個 /srv/fc 必須同一個檔案系統（jailer 用 hard link 把檔案帶進 chroot，不能跨檔案系統；jailer＝官方附的小工具，用 chroot、cgroup、namespace 把每台 VM 關起來）。`infra/scripts/fc-host-setup.sh`：印 CPU model → 檢查 /dev/kvm → `xfs_info | grep reflink=1` → 下載官方 firecracker 與 jailer 二進位（版本記進 ADR，快照不跨版本）→ 下載 Firecracker CI 版 vmlinux 6.1，用 `extract-ikconfig` 檢查 CONFIG_VMGENID、OVERLAY_FS、VIRTIO_VSOCK、PTP_1588_CLOCK_KVM，缺才自編 → 建目錄 → 裝 iproute2、nftables、chrony → jailer smoke test（API 一律用相對於 chroot 的路徑，開機印 `uname -a`）。
3. **基底映像與 volume**：現有 Dockerfile `docker export` 成 tar，`mkfs.ext4 -d` 灌成 `base-<版本>.ext4`，掛成唯讀 vda，所有沙盒共用。映像裡多放：firecracker-containerd 的 `sbin/overlay-init`（kernel 參數 `init=/sbin/overlay-init overlay_root=vdb`）、guest agent 與 pty daemon 改監聽 vsock（host 與 VM 之間不走網路的通道）、chrony 設 `refclock PHC /dev/ptp0`（ptp_kvm＝guest 直接向 host 問時間）。每沙盒 `truncate -s 20G volume.ext4` 稀疏檔掛成 vdb，同時當 overlay 可寫層與 /workspace。
4. **（A）FirecrackerRunner**：沿用第 5 步的 `snapshot(id)` 與 `fork(snapshot_id)` 介面，contract test（所有 runner 都要過的同一套測試）已含這兩條。新增 `runner/firecracker/`（runner 是 Go，用 firecracker-go-sdk）。jail 內固定相對路徑：`vmlinux`、`base.ext4`、`volume.ext4`、`snap/`、`v.sock`。
   - 網路：每沙盒一個 host netns（沿用第 4、6 步的 netns + veth + NAT + 白名單），tap 建在 netns 內，所有 guest 固定同一組 IP／MAC（快照恢復與 Fork 不用改 guest 網路）；guest 是整顆 kernel、裡面的 root 可改 IP／MAC，所以 netns 內 nftables 綁死 `iifname tap0 ether saddr <mac> ip saddr <ip> accept`，沙盒身分由 host 端 veth IP 決定。
   - create：netns／tap／nftables → jail → jailer 啟動 → PUT boot-source、drives、network、vsock、machine-config → InstanceStart → 等 guest agent 從 vsock 回 ping，10 秒沒回就 kill。
   - suspend／resume：guest `sync` 後關機、刪 tap／netns、jail 只留 volume；resume 用同一顆 volume 重新 create，冷開機 2–5 秒，記 `resumed{ms, runtime: firecracker, mode: cold}`。
   - snapshot／fork：`sync` → Paused → `cp --reflink=always volume.ext4` → Resumed；fork 是 reflink 一份冷開機。
   - control-plane：主機註冊回報 `runtime: firecracker`；`workspaces.runtime` 預設 gvisor；CLI `--runtime` 只在 dev build 出現。
5. **M2 記憶體快照**：規則寫死——一個快照＝vmstate + mem + 該時刻的 volume 副本，三者一起存一起刪（Firecracker 快照不存磁碟；記憶體裡的 page cache 指向快照當下的磁碟，磁碟改過再恢復 ext4 會壞）。Snapshot：Paused → `PUT /snapshot/create {snapshot_type: Full}` → reflink volume → Resumed → hard link 到 `/srv/fc/snapshots/<snap_id>/`；使用者終端凍住 1–3 秒，第一版接受。Suspend：同上但不複製 volume，寫完 kill、刪 tap／netns。Resume：重建 netns／tap（同名同 MAC）→ jailer 起新 firecracker → hard link 五個檔進同樣相對路徑 → `PUT /snapshot/load {mem_backend: {backend_type: "File"}, resume_vm: true}`（File 後端＝直接把記憶體檔 mmap 進來，碰到哪一頁才讀，內建延遲載入，不用自己寫 UFFD）→ 等 ping。成功後立刻把該 Suspend 快照標作廢（只恢復一次）。Fork：vmstate、mem 用 hard link 共用，volume 再 reflink 一份，走同一個 Resume，拿新 token。watchdog：resume 後 10 秒沒 ping 就 kill、退回冷開機。量測：runner 記「收到 resume」到「guest ping」的毫秒寫 `resumed{ms, runtime, mode: warm|cold}`；`infra/bench/resume.sh <id> 20 [--cold]`（--cold 每次先 drop_caches）。
6. **M2 恢復後三個坑（guest agent on-resume hook）**：(a) 網路：VM 內既有 TCP 一律當已斷，guest agent 重連 LLM proxy 與 git，host 端終端橋接重連 `v.sock` 再 `tmux attach`。(b) 時鐘：`chronyc makestep` 靠 ptp_kvm 立刻跳到正確時間（不走 NTP，會被第 6 步的出口白名單擋）；備案 host 經 vsock 傳 epoch 給 guest `date -s`。(c) 亂數與 token：VMGenID 只救 kernel 亂數池；每次 resume 與 Fork，control-plane 透過第 6 步的 proxy 輪換該沙盒的 session token。`infra/tests/resume-hooks.sh` 一次驗三項。
7. **M2 ADR 收尾與規則**：切換方式（flag 預設 gvisor、只有新沙盒派到裸機、裸機滿了自動回 gVisor）；回退（flag 關掉即回）；升級規則（快照不跨版本、不跨 CPU 型號；升級前先把 Suspend 中的沙盒喚醒重存；第二台同型號）；快照規則（Suspend 快照只恢復一次；三合一存刪；NVMe > 80% 告警）。Usage 頁那行改成「runtime: gvisor / firecracker · resume p50 / p95（冷／熱）」。

**技術選型**

| 選擇 | 理由 |
|---|---|
| Hetzner AX162（EPYC 9454P）或 Dell PowerEdge Xeon + Ubuntu 24.04 | 有 /dev/kvm 與本機 NVMe、按月租，CPU 在官方支援清單；Ryzen 桌機型號便宜但快照相容性沒人測 |
| /srv/fc 單一 XFS reflink=1 | Snapshot／Fork 複製 20 GB 稀疏 volume 只要毫秒；也是 jailer hard link 的前提 |
| Firecracker + jailer 官方 release 二進位 | E2B、Fly Sprites、Vercel 都是這條路線；File 後端載入記憶體檔本來就是延遲載入 |
| Firecracker CI 的 vmlinux 6.1 + extract-ikconfig | 省掉自編 kernel 這個最容易卡的環節 |
| firecracker-containerd 的 overlay-init + ext4 稀疏檔 | 一個檔案就是一個沙盒的碟 |
| Docker → docker export → mkfs.ext4 -d | 團隊已經會寫 Dockerfile |
| 每沙盒一個 netns + nftables 綁 MAC／IP + guest 固定 IP／MAC | 沿用第 6 步規則；快照與 Fork 不用改 guest 網路 |
| chrony + ptp_kvm | 官方文件建議的恢復後對時法，不走網路 |
| firecracker-go-sdk（只在 runner 是 Go 時） | 省掉 jailer 參數與 API 樣板碼 |

**預估**

1 人 × 4 週做完 M1（task 0–3），再 1 人 × 3 週做 M2；M1 結束有「要不要繼續」的檢查點。M1 最花時間的是 FirecrackerRunner（jailer chroot 佈局、netns／tap／nftables 搬移、pty 改走 vsock、contract test，約 2 週）；task 0 與部分 task 1 可跟 Hetzner 交機等待重疊。M2 最花時間的是三個 hook 加把冷恢復 p95 壓到目標（約 1.5 週）。

**驗收**

1. M1：乾淨裸機跑 `fc-host-setup.sh` → 印 CPU model、/dev/kvm 存在、reflink=1、四個 kernel 選項是 y 或 m、smoke test 印 guest 的 `uname -a`。
2. flag 設 firecracker，`sandbox claude` → 標籤「firecracker · ax-01」；沙盒內 `df -h /` 顯示 overlay、`mount | grep workspace` 顯示 vdb、`ls /dev/ptp0` 存在。
3. `RUNNER=firecracker` 跑 contract test（含 snapshot／fork）全綠。
4. `echo hello > /workspace/x`，suspend → `pgrep firecracker` 沒有、`ip netns list` 沒有、volume 還在；connect → 5 秒內回到 shell，`cat /workspace/x` 印 hello，Activity「Resumed in N s · firecracker · cold boot」。
5. guest 改 IP 後 `curl` proxy → 被 drop，改回來才通。
6. M2：suspend → snapshots 目錄有 vmstate 與 mem；connect → 同一個 tmux 畫面，hello 還在。
7. `infra/bench/resume.sh <id> 20` 與 `--cold` → 熱 p50 ≤ 1.0 s、冷 p95 ≤ 2 s（用 runner 的 `resumed{ms}` 量）；達不到就在 ADR 記實際數字。
8. `infra/tests/resume-hooks.sh` 三項 PASS：`date` 與 host 差 < 1 秒、`curl` 打 proxy 成功、token 不同。
9. Active 沙盒按 Snapshot → 同時有 vmstate、mem、volume.ext4，`e2fsck -fn` clean，終端凍住不超過 3 秒；Fork → 新沙盒接著同一個畫面，token 不同。
10. flag 關掉再 `sandbox claude` → 派到 gVisor，標籤顯示 gvisor。

**風險**

1. 快照三合一規則漏掉一條路徑，恢復出來 ext4 會壞且不會馬上發現：contract test 加「snapshot → fork → e2fsck 乾淨」。
2. 快照不跨 Firecracker 版本、不跨 CPU 型號：ADR 先寫升級流程與「同型號」規則。
3. 記憶體檔等於 VM 記憶體（4–8 GB），reflink 幫不了；幾十個 Suspend 沙盒吃掉上百 GB NVMe，快照只在本機：要有用量告警與保留期。
4. 冷恢復 p95 可能超過 1 秒；「約 1 秒」是研究文的預期不是承諾，用冷 bench 數字說話。
5. Active 沙盒按 Snapshot 會凍 1–3 秒；Diff snapshot 在 defer，UI 註明。
6. token 輪換依賴第 6 步的 proxy；沒做完就先禁止 Fork。
7. 團隊第一次碰 jailer 與 vsock，每個坑以「天」計，M1 可能滑到 5 週。
8. 裸機每月約 €200–250，比 Ryzen 貴三倍以上；task 0 沒算清楚會白租。
9. Hetzner 交機與網路設定是外部等待時間。

**這一步先不做**

UFFD 延遲載入（File 後端已是延遲載入；真要做用官方範例 `on_demand_handler.rs`，不抽 e2b 套件）；跨主機恢復；Diff snapshot、記憶體去重、壓縮；CPU template；Balloon 與 hugepages；多台 Firecracker 主機排程；搬既有 gVisor 沙盒；「touched N MB」顯示；GPU、virtio-fs、9p；e2b-dev/infra 的 Nomad／Consul；Morph 式無限分支 fork；計費規則調整。

## 4. 現有雛形怎麼接

雛形是單檔 `src.js`，每次事件整頁重畫（`render()` 重寫 `#app` 的 innerHTML），資料在 localStorage（`sandbox-v1`、`sandbox-policy`）與 IndexedDB（檔案）。原則是換資料來源、不重寫 UI；需要保住實例的東西（xterm、WebSocket）掛在 `#app` 外面。

| 雛形裡的畫面或功能 | 在哪一步變成真的 | 會怎麼改 |
|---|---|---|
| 側欄 workspace「Our workspace」與 profile | 2 control-plane | 改成 GitHub 頭像與「<login>'s workspace」；登入畫面只有一顆「Sign in with GitHub」 |
| 側欄 demo-card | 1 runner-mvp | 開發模式多一顆「Connect runner」按鈕（網址、token 對話框）；正式版不出現 |
| Sandboxes 頁列表、篩選、搜尋 | 1（開發模式）→ 2 | 第 1 步以 Docker 回傳重建有 runnerId 的項目；第 2 步改 `GET /v1/sandboxes`，刪掉 `save()` 與 localStorage |
| 「Try in console」與 New sandbox 表單 | 1 → 2 → 5 | 第 1 步呼叫 `POST /v1/sandboxes`（4 vCPU 選項停用）；第 2 步走控制平面；第 5 步 Repository 欄位變成真的 clone，`Cloned … (demo)` 那行拿掉 |
| QUICK LAUNCH 複製指令 | 3 cli-terminal | 複製「安裝 + 啟動」兩行，toast 拿掉「CLI 尚未實作」 |
| Terminal 分頁（模擬指令） | 1（開發模式）→ 3（第二階段） | xterm 只建一次掛在 `#xterm-host`，`detail()` 只留佔位 div；第 3 步 `terminal.js` 單例 + 一次性 ticket，「真實沙盒 ID」欄位與 `#t=<id>` 連結；沒有 remoteId 的沙盒維持模擬 |
| 「Demo session」標籤 | 1 → 3 → 8 | 「gVisor · live」→ Connecting／Live／Reconnecting／Suspended → 「firecracker · ax-01」 |
| Set idle／Suspend／Resume 按鈕 | 1 → 2 → 4 | 第 1 步 stop／start；第 2 步 `POST state`（409 就重抓）；第 4 步 `POST /v1/sandboxes/{id}/{idle\|suspend\|resume}`，Suspend 在里程碑 B 前灰掉 |
| Destroy（新增） | 1 runner-mvp | `confirm()` 後 `DELETE`，容器與 volume 一起刪 |
| 自動降級倒數（`tick()`、`[data-countdown]`） | 2 → 4 | 第 2 步以伺服器 `last_activity_at` 為基準、到期打 `auto-demo`（過渡）；第 4 步刪掉本機判斷，改讀 `next_transition_at`，`hold=agent_busy` 顯示「suspend held」 |
| Usage 頁 Auto-tiering policy 下拉 | 2 → 4 | 第 2 步 `PATCH /v1/workspace`；第 4 步 `PUT /v1/workspaces/{id}/policy`，選項值不變 |
| Usage 頁費率、session 費用、競品比較表 | 7 metering-billing | `usage()`、`cost(b)` 改吃 `GET /v1/usage`；三段 $/hr 改四維度單價並標「這段收哪幾項」；比較表「我們」那列改用四個單價算；示意值掛「示意費率」；頂端加額度進度條 |
| Usage 頁（新增）Secrets、Egress allowlist 區塊 | 6 secrets-network | 名稱、末四碼、Rotate／Remove；host 清單加刪，提示「最多 10 秒後生效」 |
| Files 頁與詳情 Files 分頁（IndexedDB 上傳、下載） | 1 → 2 → 5 | 第 1 步提示「上傳尚未接到沙盒」；第 2 步提示「檔案暫存於此瀏覽器」；第 5 步 A 段列表、麵包屑、下載、「已用 X / 10 GiB」，B 段 `tus-js-client` 續傳上傳與進度條，拿掉「每檔 10 MB」 |
| Snapshot／Fork 按鈕與 `sandbox snapshot` | 2 → 5 → 8 | 第 2 步先 disabled；第 5 步磁碟快照（含家目錄，log 改「不含記憶體」）；第 8 步 M2 記憶體快照，Fork 接著原畫面 |
| Activity 分頁（logs） | 2 → 4 → 8 | 第 2 步顯示 API 事件（created、runner=fake）；第 4 步 lifecycle_events（「No keyboard input 2m · CPU 1% → Idle (auto)」）；第 8 步「Resumed in 0.9 s · firecracker」 |
| 詳情頁（新增）Network 分頁 | 6 secrets-network | 時間｜目的地｜類型｜狀態碼｜結果，deny 紅、allow 綠，每 3 秒輪詢 |
| 詳情頁（新增）「Suspend 時 push 分支」開關 | 5 workspace-files | 只有有 repo 才顯示；旁邊「上次 push：成功／失敗原因」 |
| 詳情頁（新增）Suspend(error)／Lost 徽章與「Start fresh from workspace」 | 4 auto-tiering | 恢復失敗或主機重開過時出現，按下用 /workspace 冷開機 |
| 終端模擬指令 `sandbox ls / connect / suspend / snapshot` | 1 → 3 | 第 1 步 `sandbox ls` 改打 API；第 3 步起由本機 CLI 提供，瀏覽器內的模擬指令不再擴充 |
| Quick start 頁 | 2 → 3 | 第 2 步加「API tokens」段（Create、只顯示一次、Revoke）；第 3 步「目前沒有可安裝的 CLI」改成安裝說明 |
| 三個示範沙盒與既有時數 | 2 control-plane | seed 成 Suspend、回填事件、標「示範資料」，Usage 時數跟雛形一樣 |
| GitHub Pages 展示版 | 1 → 2 | 第 1 步完全不變（runner 模組只在開發模式）；第 2 步 `pages.yml` 改 `workflow_dispatch`，凍結在純展示版 |
| README「資料與限制」與 research.md 第 53 行 | 2 → 每一步 | 第 2 步改成「沙盒、狀態、policy 在伺服器；檔案仍在此瀏覽器」與「借 e2b 的 API 形狀，不搬程式碼」；之後每步都在同一個 PR 補自己的限制 |

## 5. 需要創辦人決定的事

1. **先只支援 Claude，還是三個 agent 一起？**
   建議：先只支援 Claude，Codex 盡力、Harness 先定義。理由：Claude Code 有完整的 hook（開始做／做完）、官方安裝器、可預填設定檔跳過首次問答，8 步的驗收都以它為準；Codex 對自訂 base_url 支援不穩、需要 Node 22 多 100 MB；Harness 目前只是 bash 殼，沒有工具名稱就沒辦法預裝。要決定的是「Harness 是哪個工具」與「Codex 要不要進驗收」。

2. **定價公式與正式費率**
   建議：公式對齊業界，拆成 vCPU-hr、記憶體 GiB-hr、磁碟 GiB-hr、快照 GiB-hr 四個維度，Active 四項都收、Idle 只收記憶體＋磁碟、Suspend 只收快照儲存；數字在 Stripe 設定，這份文件與程式碼都不猜數字。理由：研究文第 3 節第 2 點，自創一個「$/hr」讓人難比較；第 7 步已把 Stripe 當單價唯一真相，佔位費率沒換掉切正式模式會被程式擋下。要決定的是四個數字，以及 80% 額度是否要寄信（目前只做橫幅）。

3. **裸機要不要租、租哪裡**
   建議：現在不租。等第 8 步的閘門：gVisor 冷恢復 p95 超過 5 秒、或有客戶明確要求 VM 等級隔離，才 go。要租就選 Hetzner AX162（EPYC 9454P）或 Hetzner Dell PowerEdge Xeon 機種，不租 Ryzen 型號，第二台同型號；留在 AWS 的話要 .metal 機型，成本另算。理由：裸機每月約 €200–250，M1 + M2 要 7 週，而 gVisor 版已經能 Suspend／Resume；先用數字決定，別先花錢。

4. **網域、帳號與花費上限（第 2 步任務 0，創辦人可以自己做大半）**
   要決定：網域（固定用 `console.<網域>`、`api.<網域>`）；VPS 與 VDS 供應商（第 1 步要 KVM 型，不要 OpenVZ／LXC）；GitHub OAuth App 兩個（本機、正式）；備份 bucket（Cloudflare R2 或 S3）；Anthropic Console 幫 runner 那把 key 設每月花費上限（計劃裡的例子是 US$50）。建議：能開的帳號在第 1 步進行中就先開，因為第 2 步半週都在等 DNS 生效與帳號審核。

5. **第 8 步 M2（記憶體快照）與第 4 步里程碑 B 是不是必做**
   建議：都設成「有檢查點、可以停」。第 4 步的 spike 做不通就停在自動 Idle（已經是可以對外講的成果）；第 8 步 M1 結束可以只交付 VM 等級隔離。理由：這兩段是整份計劃最容易滑期的地方（checkpoint／restore、jailer、vsock 每個坑以「天」計），先把「自動降級、檔案持久、祕密不進沙盒、能收費」做完再回頭，對產品故事的影響最小。要決定的是「約 1 秒恢復」要不要當對外承諾——建議只說「Suspend 不收運算費、恢復回到同一個畫面」，秒數等 bench 數字。

## 受邀試用版：工程對照與待決策邊界


以下是短版移入的工程對照；其餘詳細步驟尚待同步，#7 保持開啟。兩個產品取捨已於 2026-09-21 由創辦人決定：先邀 3 到 5 人受限試用、不設預設運行時限。語言已定案：Runner 與 CLI 用 Go，見 [Runner 語言 ADR](adr/runner-language.md)。

| 題目 | 首版方向與驗收 |
|---|---|
| 使用者 | 僅受邀、有長任務或多 session 需求的個人開發者；先只支援 Claude 與 API key。邀請名單及跨租戶授權為必要條件。實際邀請數依容量與放行驗收決定。 |
| 產品價值 | 交付任務、關閉客戶端一小時、重新連線取回成果。公開 repo clone、使用者主動 git push，以及只下載的 sandbox cp 為最小路徑。push 失敗或無寫入權限仍能下載；大型續傳、檔案 UI 擴充與 Snapshot／Fork 延後。 |
| 冷 Suspend | 停止程序、保存 workspace 與選定家目錄資料。保存 session ID 並以明確 session 恢復對話；不能保證同一程序／畫面。找不到紀錄時明示並提供新 session，不默默接到另一段對話。斷線本身不停止程序。 |
| 自動狀態 | 自動 Idle 與自動 Suspend 分開驗收；依下方規則保護背景任務。限速可能影響延遲與逾時，不能描述成沒有代價。 |
| 費用 | 試用不收費，使用者自帶專用 API key；從第一個真 Runner 開始記錄生命週期與資源事件。Usage 先顯示可核對的用量；費用只在有版本與生效日期的假設費率下作估算，競品比較需同規格且標明來源日期。 |

**狀態規則**

1. Active → Idle：可用無互動、低 CPU 與 Agent 訊號作判斷，但已知忙碌／長任務需保護。CPU 需求、任務重新開始或使用者輸入都應觸發恢復 Active；門檻與反覆切換抑制由測試決定，不先承諾固定 30／60 秒。
2. Idle → cold Suspend：收到對應目前 session／generation 的有效完成訊號，且沒有仍在執行的受管任務，再開始倒數。新活動取消倒數；單次回覆結束不等於所有背景程序結束。訊號缺失、過期或無法確認任務狀態時，不自動 Suspend。
3. 最長運行時數是獨立的使用者政策，不是假裝閒置：已決定平台不預設時限，由使用者自行啟用；不能把 12／24 小時上限當成閒置判斷。若啟用，建立時顯示期限、提前提醒、允許延長，並明示到期冷 Suspend 會中斷執行中工作。時限預設值、額度耗盡及主機緊急處置須在 #7 確認後才能實作。
4. 主機容量、每人配額、磁碟限制與獨立 watchdog 另外控制資源，不靠「長時間一定暫停」替代。每人 running 配額與「同時兩個沙盒」驗收必須一致；未實測前不宣稱 16 GB 一定可跑特定數量。

**資料與憑證保存**

- workspace、Claude 對話與必要設定可持久化；shell history、gh 登入及其他憑證不能不加區分地納入一般備份。
- #7／#12／#21 交付保存矩陣：每類資料的儲存位置、明文可讀者、備份排除或加密規則、保留期限、刪除與撤銷方式。
- CLI 重送 key 不代表平台從未處理明文。邀請說明需精確描述執行期注入與存取邊界；禁止把 key 寫入一般 DB、log、映像或一般備份。若設計允許沙盒程序讀取，必須明示此限制。
- API 費用上限依供應商實際支援的帳號／workspace 層級驗證，不保證任意單把 key 都能獨立設限。冷恢復後需要重新送入的憑證須有明確流程。

**外部試用放行與順序**

先完成 #7 契約 → #8 相容性驗證 → 最小 Runner／CLI／下載／持久化 → 自動狀態與事件計量 → 外部試用驗收。正式 Stripe 收費、暖恢復與 Firecracker 留到後續。

現有 #24 追蹤完整 Alpha，包含 #21／#22 的憑證代理與網路等依賴。這是目前票的範圍，不是使用者已選擇「第一位外部使用者必須等到完整 Alpha」的證據。

- 已選先邀 3–5 人受限試用：需另開受限試用放行票，列出隔離、憑證、內網／metadata、容量、備份還原與事故處理的具體措施，以及哪些能力延後、剩餘風險與核准人。必要時調整相依圖，不把 #24 未完成誤當這批試用已通過完整 Alpha。
- 拆票前不移除 #24 的現有依賴，也不把風險揭露當成技術措施；擴大邀請仍以完整 Alpha 為門檻。

原 1 人約 13 週／2 人約 10–11 週僅保留為未驗證目標，不作交期，也不聲稱與原第 20.5 週範圍完全相同。下載、家目錄、憑證與隔離等已前移工作需計入；完成 #8 與選定終端方案後，依各票重估關鍵路徑與緩衝。

**尚待定案與文件同步**

- 受限試用放行票：隔離、憑證、內網／metadata、容量、備份還原、事故處理的具體底線與揭露文字。
- 使用者自訂運行時限的設定入口、提醒與延長規則；每人配額與主機容量的數字。
- 資料與憑證保存矩陣，以及 #24 放行證據。
- plan-detail.md 的三 Agent、暖恢復、回收器、backup、secret 與計費段落須同步修訂；完成前仍屬歷史設計參考，不據此繞過本節與 #7 的必要確認。
