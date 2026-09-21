# 實作計劃：短版（2026-09）

> 語言配置正在收斂：見 [語言配置提案](language-proposal.md)。Runner 不再預排 Node → Go 重寫；最終語言待團隊維護能力確認，原語言與估時描述暫作歷史設計參考。

> 從現在的瀏覽器雛形，到「一行 `sandbox claude` 真的能跑、能暫停接續、能收費」，拆成 8 步。每步的估時是 **1 位工程師** 的週數；2 人時第 1、2 步和第 5、6 步可以並行。每步的具體做法、指令、驗收與風險在 [plan-detail.md](plan-detail.md)。

## 原則

1. **每一步做完都要看得到**：不是「後端好了」，而是你能在雛形或終端機親手操作到。
2. **先 gVisor 後 Firecracker**：一般租用的虛擬主機沒有硬體虛擬化，先用 gVisor（Google 的沙盒執行器，不需要特殊硬體）；Firecracker（AWS 的微型虛擬機）要租裸機，留到最後，而且先用數字決定值不值得。
3. **能用開源就不自己寫，但不引進超出團隊能力的平台**：Docker、tmux、xterm.js、Caddy、Stripe 直接用；Nomad、K8s、Vault 不碰。
4. **先單租戶、單機**：一台 VPS 跑控制平面，一台 VDS 跑沙盒。
5. **先做 Claude**：驗收都以 Claude Code 為準，Codex 盡力，Harness 等定義清楚是哪個工具再說。

## 總覽

| 順序 | 步驟 | 做完你會看到什麼 | 預估 | 依賴 |
|---|---|---|---|---|
| 1 | 真沙盒（gVisor） | 雛形的 Terminal 分頁變成真的 shell，打 `claude` 直接進 Claude Code；Suspend 後檔案還在 | 3 週 | 無 |
| 2 | 控制平面與登入 | 用 GitHub 登入，沙盒清單、狀態、倒數存在伺服器，換台電腦看到同一份；可發 API token | 3.5 週 | 無 |
| 3 | CLI 與終端串流 | 自己電腦裝好 `sandbox`，`sandbox claude --repo URL` 10 秒內接上雲端終端；關掉再 `sandbox connect` 畫面還在 | 5 週 | 1、2 |
| 4 | 自動降級 | 沒人敲鍵盤就自己 Active → Idle → Suspend；Agent 跑長任務不會被誤暫停；B 段從記憶體快照 1–3 秒回到同一畫面 | 5 週 | 1–3 |
| 5 | 檔案與工作區 | 每沙盒一顆真磁碟；從 repo 真的 clone；Files 分頁列真檔、500 MB 續傳上傳；Snapshot／Fork 帶著檔案走 | 4 週 | 1–4 |
| 6 | 祕密與網路出口 | 沙盒裡找不到真 API key 但 Claude 照常回答；對外連線預設全擋、白名單放行；Network 分頁看每筆連線 | 4 週 | 1–4 |
| 7 | 計量與收費 | Usage 頁是伺服器算的真數字；額度到了自動 Suspend；Stripe 測試模式出帳、每晚對帳；掛了會收 email | 5 週 | 1–5 |
| 8 | Firecracker 與裸機（可選） | 先用 gVisor 數字過閘門；A 段 VM 等級隔離；B 段約 1 秒恢復 | 4 + 3 週 | 1–7 |

**累計**：到能收費（第 7 步）29.5 週，含 15% 緩衝約 34 週；第 8 步另加 7 週。2 人並行約 22.5 週到能收費。

**為什麼這樣排**：第 1 步最快讓你看到真東西，而且線上展示版完全不動。第 3 步是產品入口。第 4 步是我們相對 E2B 的核心賣點（不為等 LLM 付全價），也是收費的資料來源，所以排在檔案與祕密之前。第 8 步開頭是一個不花錢的閘門：gVisor 版恢復夠快、又沒客戶要求 VM 隔離，就整步不做。

## 里程碑

| 里程碑 | 步驟 | 達成後對外可以說 | 累計 |
|---|---|---|---|
| M1 `sandbox claude` 真的能跑 | 1–3 | 一行指令接上雲端沙盒，clone 完自動進 Claude Code；斷線再接回畫面還在 | 11.5 週 |
| M2 關掉電腦明天回來能接續 | 4–5 | 沒人用就自動降級；恢復後檔案、登入狀態都在；從 repo 建立、Snapshot／Fork | 20.5 週 |
| M3 能給外人用、能收費 | 6–7 | 沙盒裡沒有真 key、出口白名單；Usage 真數字、額度上限、Stripe 出帳 | 29.5 週 |
| M4（可選）VM 隔離與秒級恢復 | 8 | Firecracker 微型虛擬機，Suspend 後約 1 秒回到同一畫面 | 36.5 週 |

## 各步驟一頁摘要

### 1. 真沙盒（3 週）

- **目標**：在一台 VPS 上用 Docker + gVisor 跑隔離容器，Claude Code 在裡面執行，畫面即時串到雛形的 Terminal 分頁。
- **做完會看到**：開發模式按「Try in console」，Terminal 變真 shell；`uname -r` 印 gVisor 的假核心版本；Suspend 後 Resume，檔案還在。線上展示版不變。
- **最花時間**：把 tmux 畫面接進雛形而不閃爍、不斷線。
- **先不做**：多主機、多租戶、登入、檔案上傳、計費。

### 2. 控制平面與登入（3.5 週）

- **目標**：沙盒清單、狀態、倒數、policy 離開瀏覽器，改由 VPS 上的 API 與 Postgres 記住；GitHub 登入；發 API token 給之後的 CLI。
- **做完會看到**：開 `console.<你的網域>` 登入，看到跟現在幾乎一樣的畫面；換台電腦同一份；第二個帳號是空清單；每天自動備份。
- **最花時間**：前端每個動作改成「送出、等回應、重畫」，要一個畫面一個畫面對照。
- **先不做**：接真 runner（第 3 步開頭）、終端串流、多人 workspace、其他登入方式。

### 3. CLI 與終端串流（5 週）

- **目標**：先把第 1 步的 runner 接進控制平面，再做可安裝的 `sandbox` CLI：`claude|codex|harness`、`ls`、`connect`、`suspend`、`snapshot`，以及瀏覽器內同一個畫面。
- **做完會看到**：Mac 上 `curl … | sh` 裝好，`sandbox claude --repo URL` 10 秒內看到 clone 進度、自動進 Claude Code；Ctrl-\ 脫離、`sandbox connect` 接回。
- **最花時間**：CLI 接終端的邊角（Ctrl-C 透傳、視窗大小、重連），以及讓 Claude Code 跳過首次問答。
- **先不做**：閒置判斷、API key 代理、port forwarding、Windows 版、自動更新。

### 4. 自動降級（5 週，A 段 1 週可先 demo）

- **目標**：沒人敲鍵盤、Agent 做完在等人時，自己降到 Idle 再到 Suspend；Agent 在跑長任務時不會被誤暫停。A 段是冷 Suspend（停容器留檔案），B 段升級成記憶體快照。
- **做完會看到**：詳情頁倒數由伺服器算，歸零徽章自己變 Idle、再變 Suspend；打一個字 1 秒內跳回 Active；B 段 `sandbox connect` 印「Resuming from snapshot… 3.2s」回到同一個 tmux 畫面。
- **最花時間**：把 gVisor 的 checkpoint／restore 接回終端與 tmux 重連，以及失敗後的清理。B 段有可行性試做，做不通就停在 A 段，不算延期。
- **先不做**：Firecracker 快照、跨主機恢復、每沙盒個別 policy。

### 5. 檔案與工作區（4 週）

- **目標**：每個沙盒一顆真的、會保留的磁碟；從 repo 建立；瀏覽器與 CLI 上傳下載含大檔續傳；Snapshot／Fork 帶著檔案與登入狀態；Suspend 前可選 push 分支。
- **做完會看到**：Repository 欄位真的 clone；Files 分頁列真檔、麵包屑、「已用 X / 10 GiB」；拖 500 MB 進去有進度條、拔網路會續傳；`sandbox cp` 雙向複製；快照標「保留至 <日期>」。
- **最花時間**：續傳上傳整條鏈，約 1.5 週；其次是路徑安全。
- **先不做**：記憶體快照 fork、私有 repo 憑證、檔案版本歷史、線上編輯器。

### 6. 祕密與網路出口（4 週）

- **目標**：沙盒裡找不到任何真 API key，但 Claude 照常回答；對外連線預設全擋、白名單放行；每筆連線有紀錄。
- **做完會看到**：`sandbox secrets set` 貼 key 只印末四碼；沙盒裡 `env` 只看到 `sandbox-managed`；`curl example.com` 一秒內被擋，加進白名單 10 秒後通；詳情頁多 Network 分頁。
- **最花時間**：每沙盒獨立網路與防火牆反偽造，做錯就是跨租戶用到別人的 key，所以 M3 前請外部工程師花 1 天審過。
- **先不做**：Vault 產品、TLS 攔截檢查、短效祕密輪換、inbound 預覽網址。

### 7. 計量與收費（5 週）

- **目標**：每次狀態切換記成伺服器蓋時間戳的事件，用同一條計算路徑算出 vCPU-秒與 GiB-秒；Usage 頁、額度上限、Stripe 三處看到同一份數字；單價以 Stripe 為唯一真相；每晚對帳。
- **做完會看到**：Usage 頁改成四個維度（vCPU、記憶體、磁碟、快照）並標「這段狀態收哪幾項」；頂端「本期已花／上限」進度條；Stripe 測試模式的發票數量跟頁面一致；服務掛了或備份失敗會收到 email。
- **最花時間**：跨整點、跨月、resize、失聯重連這些邊界，以及對帳的多算抵、少算補。
- **先不做**：預付點數、優惠券、多幣別與稅、LLM token 計費、監控平台。

### 8. Firecracker 與裸機（可選，4 + 3 週）

- **目標**：先用 gVisor 版的恢復速度數字確認值得做；值得才租一台裸機跑 Firecracker，A 段拿到 VM 等級隔離，B 段做記憶體快照約 1 秒恢復；上層 API、CLI、畫面都不改，用工作區層級開關切換與回退。
- **做完會看到**：Usage 頁多一行 gVisor 恢復 p50／p95 與 go／no-go 結論；打開開關後 `sandbox claude` 拿到裸機 VM，標籤變「firecracker · ax-01」；B 段 Activity 顯示「Resumed in 0.9 s」。
- **最花時間**：把網路、終端通道搬進 VM（約 2 週）；B 段把恢復時間壓到目標。
- **先不做**：跨主機恢復、多台裸機排程、GPU、搬既有 gVisor 沙盒。

## 現有雛形怎麼接

換資料來源、不重寫畫面。對照表（每個畫面在哪一步變成真的）在 [plan-detail.md 第 4 節](plan-detail.md#4-現有雛形怎麼接)。重點：

- Terminal 分頁：第 1 步變真 shell，第 3 步改成正式的串流。
- Sandboxes 清單、狀態按鈕、倒數、policy：第 2 步進伺服器，第 4 步改讀伺服器的自動降級。
- Files、Snapshot／Fork、Repository 欄位：第 5 步變真的。
- Usage 頁費率、比較表、額度：第 7 步改吃真數字。
- 線上展示版：第 1 步完全不動，第 2 步起凍結成純展示版。

## 需要你決定的事

1. **先只支援 Claude，還是三個一起？** 建議先只 Claude；Codex 對自訂 API 位址支援不穩；Harness 要先講清楚是哪個工具。
2. **定價公式**：建議拆成 vCPU-hr、記憶體、磁碟、快照四個維度，Active 全收、Idle 只收記憶體＋磁碟、Suspend 只收快照儲存。四個數字由你在 Stripe 設定，程式碼不猜數字。
3. **裸機要不要租**：建議現在不租，等第 8 步閘門的數字。要租就選 Hetzner 的 EPYC 或 Xeon 機種，每月約 €200–250。
4. **網域、帳號、花費上限**：網域、VPS／VDS 供應商（要 KVM 型，不要 OpenVZ／LXC）、GitHub OAuth App、備份 bucket、Anthropic key 的每月上限。這些能在第 1 步進行中就先開，第 2 步有半週在等 DNS 與審核。
5. **記憶體快照要不要當對外承諾**：建議只說「Suspend 不收運算費、恢復回到同一個畫面」，秒數等實測數字；第 4 步 B 段與第 8 步 B 段都設成「可以停」。
