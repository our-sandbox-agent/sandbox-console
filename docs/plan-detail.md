# 實作計劃：工程版

本版同步創辦人已決定的 Go／先受限試用／無預設運行時限。它取代舊 8 步正文；舊實驗指令與估時保存在 [4033a91 歷史版本](https://github.com/our-sandbox-agent/sandbox-console/blob/4033a91/docs/plan-detail.md)，不得將歷史回收器、暖恢復或收費承諾當成當前契約。

讀者入口：[短版](plan.md)、[語言 ADR](adr/runner-language.md)、[生命週期 ADR](adr/sandbox-lifecycle.md)。生命週期 ADR 是狀態、API、保存與任務保護的唯一詳細契約，以下不維護第二套狀態表。

## 1. 架構與邊界

| 元件 | 技術／責任 | 不負責 |
|---|---|---|
| Console | 現有 JavaScript/Vite；明示 demo 或 real API 模式 | 不保存正式 key、不在前端推算權威狀態 |
| 控制平面 | TypeScript、Hono、Postgres；授權、operation、事件及對帳 | 不把 HTTP 202 當成 runtime 成功 |
| Runner | Go；Docker + runsc adapter、容量、generation／fencing、runtime observation | 不在同一程序內自稱 host watchdog |
| CLI | Go；安全認證、create/connect/state、基本下載 | 不繞過控制平面直接呼叫 Runner |
| 宿主監督 | 獨立 lease watchdog、容量／磁碟與 incident 訊號 | 不以未知狀態默認程序已停止 |

受限試用是多使用者授權、單 Runner 部署；單機不等於可省略租戶隔離。對外固定一個 `console.<domain>` 提供 UI、API、WebSocket；Runner 僅私網、每次驗 service identity。內部實驗可用 loopback＋授權的 SSH tunnel，不能把實驗 token 當正式登入。

## 2. 里程碑與依賴

以 GitHub 原生 blocked-by 為排程來源。M0=#2 規格／可行性、M1=#3 內部啟動、M2=#4 完整 Alpha、M3=#5 收費、R=#6 研究。受限試用是 M1 後的獨立放行點；文件不再用 A/B 命名暗示暖恢復必做。

- #7 → #8 與 #9；#46 與 #7 契約對齊。
- #8 go 才做 #10；#8 go 且 #9 完成才做 #11。映像檔和 Runner 可並行，但不宣稱 gVisor 之外沒有技術未知。
- #12 在 #10/#11 之後；#13 依映像檔／Runner 接 terminal；之後 #14 CLI、#15 real console。
- #52 IDE 模式 spike 在 #8、#10、#11、#13 之後，M2 timebox；不阻擋受限試用。
- #16 起的授權、#17 operation、#18 watchdog、#19 policy、#20 files、#21 secrets、#22 network、#23 operations 各自保留功能驗收；受限試用只可對其中必要子範圍填證據，不能把整票提前關閉。
- #24 仍是完整 Alpha，保留其全部依賴。#46 只定義受限試用規格，完成後另按清單執行實際放行，不解除 #24。
- #9 的事件契約在第一個真 Runner 使用；#25–#30 的持久帳本、計價、Stripe、對帳和正式放行逐步接上。
- 暖恢復、Snapshot/Fork、續傳及 Firecracker 不阻擋檔案／網路／secrets。沒有要求先 raw runsc 重寫才能做基本功能。

## 3. 本輪交付

### T00／#7：契約

交付 [生命週期 ADR](adr/sandbox-lifecycle.md)、本計劃及短版。驗收對照：

| #7 驗收 | 落點 |
|---|---|
| 斷線／cold／warm 語意 | ADR §1 |
| 統一狀態及 /state | ADR §2–3，涵蓋 Lost/Error、operation、409、fencing |
| 固定 Runner 語言 | Accepted 語言 ADR；第一版 Go，無暫時 Node |
| 保存矩陣、任務保護及首版範圍 | ADR §4–6 |
| 修正文件與命名 | 本文件與短版；一個公開 domain，M0–M3＋R，無 A/B 前置假設 |

合併 #7 的規格不代表其所有 runtime 案例已通過。其後各票按 ADR 產生實測證據。

### T01／#8：限時相容性矩陣

2–3 工程人天是試驗上限，不是承諾通過。需要已授權 Linux 主機、Docker 中註冊 runsc、固定 image digest／Claude 版本與憑證配置；沒有環境標 waiting environment。

必做：環境版本與 runtime 設定、shell、公開 repo clone、套件安裝、Claude marker、PTY resize／detach/reconnect、CPU／memory／PID 限制、workspace／home cold restart。實際量測而非只 inspect 設定；`uname -r` 不是唯一隔離證據。runc 只作診斷對照，不能替代 runsc pass。不得將 key／完整環境／憑證放 log。

結果逐列 pass/fail/not-run；必做列缺失則沒有 go。no-go 附可重現失敗及可行縮小範圍，等待另次決策。測試只建立帶唯一 test label 的 disposable 資源；不得清理未知容器或既有資料碟。

### T02／#9：事件與帳本語意

必含 operation_id、generation、sequence、recorded/effective_at、同狀態 resize、sandbox／volume／snapshot 獨立資源及 Lost 不確定區間。UTC、半開區間、固定最小單位、版本化 rate card；試用不收費。手算案例與機器可驗 fixture 是契約驗證，不是正式 billing engine。

### T03／#46：受限試用放行規格

3–5 人範圍與創辦人決定一致。列出最低控制、證據格式、責任人及揭露草稿；這張規格票合併不代表邀人授權。完整 API key proxy／完整出口 allowlist 可列延後，但內網與 metadata 阻擋、隔離、憑證不落一般 log/backup 等最低控制必須驗證。

## 4. 後續實作規格

### 映像檔與 Runner（#10／#11）

Go adapter 隔離 Docker 呼叫，image digest、runsc、Claude 版本固定並記錄相容矩陣；Agent 第一版只有 Claude。非 root、必要 capabilities、PID／CPU／memory／disk 上限及 host headroom 由實測決定，不能 8 GB 主機直接配兩個 4 GB。

create 原子預留租戶與主機容量，Runtime 必須為 runsc；權威 state 依觀測推進；timeout 與 crash 交給對帳。所有變更需 idempotency、generation 及 fencing；destroy 未確認資源釋放前不歸還容量。沒有按存活 4 小時／停止 24 小時自動回收的開發期捷徑。

### 資料與終端（#12／#13）

workspace 與 home 分開；home 只保存已選定非敏感設定／對話，runtime credentials 另放 ephemeral storage。具體備份、destroy 與重送流程按 ADR 矩陣。先驗證 cold persistence；暖 checkpoint 不作前置。

只選一套 terminal transport，以 #8 的 PTY 相容結果決定 ttyd 或薄 PTY adapter，不預排替換。CLI／Web 使用同協定；驗 raw mode、Ctrl-C、resize、detach、重連、斷網與停止中的 409。tmux 斷線保留與冷恢復新程序分開驗收；不驗「stop/start 原 PID 還在」。

### CLI、Console 與檔案（#14／#15／#20）

最小命令：login、claude、ls、connect、suspend、exec 及只下載 cp。CLI 帶 token 呼叫控制平面，token 本機受限權限；安裝產物按 OS／arch 驗證，不承諾未測平台。使用者主動 push 不替代下載；不自動 force push／commit，不把個人 git 憑證寫進映像。

Console real API 模式顯示 pending operation、Lost／Error 及錯誤處理；demo localStorage 與真服務明確分隔。#39/#41 暫緩，等 real API 接回再評估是否還需要同一套 UI。

cp 下載驗租戶／沙盒／路徑，防 symlink 與目的地解壓逃逸；Suspend 可只讀，不改寫或刪除檔案；檔案寫入恢復後進行。安全路徑實作按選定 Go 版本官方 API 確認，不猜行數或把未驗 API 行為當保證。資料夾上傳簡單版進受限試用（#20 補充：打包直傳 volume、固定大小上限、忽略清單、UI 顯示被排除檔案）；大檔續傳與檔案 snapshot 留後續。

IDE 模式（#52）若通過 spike，是每沙盒可選附加：code-server 與 Agent 同容器同 home、經 `console.<domain>/s/<id>/ide/` 子路徑代理、整合終端只是 tmux 的另一個客戶端；Idle 訊號以使用者輸入為準並排除 IDE 程序（#19）。

### 登入、狀態與營運（#16–#23）

GitHub OAuth + invite allowlist，所有資源操作重新驗 workspace 授權；workspace ID 不是授權。單一公開 domain；HTTP／WebSocket、下載及 operations 都有相同授權邊界。

operation 狀態與 runtime observation 分離，失聯時保留容量並標 Lost；host watchdog 在 runner crash 下仍有效。自動 Idle 看 busy/unknown 保護與限速指標；自動 Suspend 只在已確認任務完成後倒數；無 hook 不當成結束。使用者選的 deadline 是另一個 reason；預設 null。

受限試用 key 可被沙盒程序讀取，揭露、ephemeral 注入、撤銷與清理必須測試。CLI/API request body、trace、shell history、images、一般備份不能記 key。home 備份不能整包包含 gh token。完整代理進 #21，但不能以延後代理為由省略基本憑證措施。

網路先驗 host/control-plane／其他租戶／RFC1918／link-local／metadata 等路徑阻擋（含 IPv6、DNS rebinding 和既有連線處理）；保留必要對外 clone／套件／模型連線。完整 domain allowlist 另於 #22 完成，不以網路清理失敗 destroy 使用者 volume。

backup 是 allowlist 匯出、加密儲存、受限讀取與還原演練；RPO/RTO、保留天數和刪除流程要在放行表填值。未知錯誤預設停止新增 allocation 並隔離故障執行實體、保留可救資料；沒有固定運行期限不代表無主機容量／磁碟配額。

### 計量與正式收費（#25–#30）

事件從 Runner 第一版記錄。Active／Idle／Suspend 的實際資源量和未來收費政策分開：Idle 仍可能有 CPU，cold Suspend 仍有 workspace/home 儲存。snapshot 是另一個資源，過期不是 sandbox.destroyed。同狀態 resize 也要事件。

DB 帳本為可核對資料源，費率有版本／生效日；Stripe 是後續結算整合，不是覆蓋歷史價格的四列配置。Lost 區間標 uncertain，恢復證據以校正事件補足，不覆寫舊事件。試用 Usage 顯示數量及清楚標示的估價，未確定區間不偽裝精確金額。正式收費另有測試出帳、shadow billing 與明確 go-live。

### 可選研究（#31–#38）

checkpoint、Fork、500 MB 續傳、自動 push 與 Firecracker 各有獨立 go/no-go。Docker checkpoint 與 raw runsc 都可作研究候選，不先假設一定要換底層。Firecracker 主機需實際確認 KVM 權限，不能用「一定裸機」或特定恢復秒數代替驗證。SDK 覆蓋依語言 ADR，必要時直接打 API；此輪不購機、不寫 VM backend。

## 5. 驗收與交付節奏

每張票有獨立分支與 PR，CI 通過且人工審查後才合併；上游規格未合併的下游 PR 標示依賴。不因寫好 spec 就把功能票關閉。文件變更用連結／衝突檢查；程式變更用對應單元及整合測試，runtime 必須附原始 log 和環境版本。

本輪 #7／#9／#46 合併且 #8 得到 go 才能把 M0 視為足以啟動預定 M1 範圍。若 #8 等待環境，其準備工作可以交 PR，但 M1 #10/#11 不解除等待。
