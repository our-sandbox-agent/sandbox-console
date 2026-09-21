# 生命週期事件與資源帳本

Proposed，2026-09-22。Closes #9；依賴 [#7 生命週期契約 PR](https://github.com/our-sandbox-agent/sandbox-console/pull/47)。本輪定義語意及可驗算案例，不實作 DB、Runner 或收費系統。費率範例都是虛構測試值。

## 1. 事件信封與順序

每筆不可變事件包含 `schema_version, event_id, tenant_id, workspace_id, resource_type, resource_id, sandbox_id?, operation_id?, generation?, source_id, source_seq, ledger_seq, recorded_at_ms, effective_at_ms, type, reason, payload, evidence_ref, certainty`。所有時間為 UTC epoch 整數毫秒；無 key、命令全文或專案內容。

- `event_id` 全域唯一；`(source_id,generation,source_seq)` 唯一。完全相同重送回原收據；相同鍵不同內容隔離並告警，不能覆蓋。外部 API idempotency 與帳本 event 去重是兩層。
- Runner 在同 generation 持久化 source_seq；重啟不能歸零冒充新事件。執行實體更換才換 generation，控制平面 fencing 拒絕舊 generation 的即時寫入；歷史補件另走經驗證的 reconciliation，不可改現況。
- `ledger_seq` 是控制平面按資源提交的單調序號。缺 source_seq、衝突或時鐘不可信先標 unresolved；不能依 HTTP 到達順序直接結帳。相同 effective 時刻按經確認的 source 順序，零長區間用量為零。
- `recorded_at_ms` 是 DB 收到事件的時刻；`effective_at_ms` 是已驗證效果發生時刻，晚到的事件不得改用收到時間。Runner 同時保留 boot ID、單調時鐘及 UTC 對時錨點；跨 boot、時鐘倒退或誤差超過放行配置門檻，區間 uncertain，不猜負時長或靜默 clamp。
- 控制平面接受 requested event 不等於 runtime applied。只有確認觀測才切資源區間；失敗請求可以有 audit event，但不產生不存在的已套用資源量。狀態與 outbox 同 DB transaction，外送失敗可重送；無 runtime/DB 跨系統原子保證。

## 2. 事件種類與資源

| 類型 | 必要 payload／語意 |
|---|---|
| operation.requested/failed/succeeded | operation ID、目標、expected_version、generation、結果；稽核而非直接算用量 |
| runtime.started/stopped | instance ID、generation、確認時間及初始政策；程序確認停止才停止 compute 區間 |
| policy.applied | Active/Idle、完整新資源配置、前版本；同狀態 resize 也發事件 |
| resource.provisioned/resized/released | resource ID、kind、完整 quantity 向量；只計已配置量，容量 admission reservation 另記不可混為用量 |
| heartbeat.confirmed/lease.expired | 最後觀測、lease、instance/generation、完整資源摘要；Lost 是知識不確定，不是 release |
| snapshot.created/expired/deleted | 獨立 snapshot ID、size bytes、實際建立／確認刪除時刻；TTL 到期只發刪除請求，確認刪除才結束儲存 |
| correction.accepted | 被取代區間／事件 IDs、替代事件 IDs、證據、原因、批准者；append-only，不改原始紀錄 |

sandbox runtime、workspace volume、home volume、snapshot 各有獨立 resource ID。冷 Suspend 停 compute，volumes 繼續；sandbox destroy 不能順便假定備份或 snapshot 已刪除。retention deadline 與實際 release 都保留。volume resize 不能只依 sandbox state 推導。

### 數量，不先混入價格

| meter | quantity 整數單位 | 積分單位／取樣依據 |
|---|---|---|
| cpu_reserved | milliCPU | milliCPU·ms；已套用 CPU quota，1 vCPU=1000 milliCPU；不是 CPU busy time |
| memory_reserved | byte | byte·ms；已套用 memory allocation |
| volume_provisioned | byte | byte·ms；已配置儲存額度，非檔案實際使用量 |
| snapshot_stored | byte | byte·ms；儲存服務確認的快照計量大小；壓縮／共享扣量另版政策 |

Active/Idle 收集 CPU 與 memory；Idle CPU 若仍有配置不可報 0。Suspend 只剩已存在 storage。若只有 admission reservation、尚未配置 runtime，保留 reservation 稽核但不冒充 runtime 使用。實際 CPU busy／磁碟使用另外監控，不拿它替換上述計量單位。

每個確認配置形成 `[start_ms,end_ms)` 半開區間，向量 `quantity × duration` 使用任意精度整數。不得用 JavaScript Number 存 byte·ms。狀態轉移／resize／資源 release／費率邊界／UTC 月界都切段，且不能重複累計。同時刻先終止舊向量再啟用新向量。

## 3. Lost 與校正

最後可信 heartbeat 時刻 H 到新證據時刻 R 是 uncertain，不是假定全程 Active，也不是免費停止。可確認部分只累計到 H，Usage 顯示「至少 X，另有待核對區間」，不能把下限當完整帳單。實際容量仍保留至 fencing／停止確認。

恢復取得可信 stop/resize 記錄後，append correction 取代 affected projection，重算相交區間。保留原版和新版、誰批准、證據及差額；晚到舊 generation 只能經此路徑補歷史，不能啟動或停止現 generation。無法確認的區間維持未解決，正式出帳前需人工處理，不能靜默轉成零或收滿。

月結快照固定事件 watermark、correction revision、rate IDs、未解決區間。關帳後 correction 以補充／折讓項關聯原帳單，不偷偷改已付金額。試用只展示估算，未收取款項。

## 4. 費率與四捨五入提案

immutable rate card 含 `rate_id, version, currency, meter, state?, effective_from_ms, effective_to_ms, numerator_minor, denominator_meter_units, rounding_policy`。相同價格 key 的有效區間不得重疊；缺費率顯示未定價，不能默認 0。修改費率建新版本及生效時間，不覆蓋過去；同一 bill line 不能混幣種。

價格以最小貨幣單位的有理數表達：`cost = integrated_meter_units × numerator_minor / denominator_meter_units`。例如每 vCPU 小時 100 cents，分母為 `1000 × 3600000` milliCPU·ms。GiB 為 `2^30` bytes，沒有 GB/GiB 混用。使用整數／有理數，不用浮點或每秒 rounding。

先按 UTC 月份、workspace、currency、meter 彙總所有確認切片（含不同 rate versions），最後每 line 一次 round-half-up 到整數 minor unit。帳單總額加總已 round 的 line。相同規則用於明確標記的試用估價；正式價目和收費啟用仍需後續決策。negative adjustment 以絕對值 half-up 後恢復符號，禁止依語言預設 bankers rounding。

## 5. 可驗算案例

[fixtures](../contracts/ledger-examples.json) 列的是已驗證的 projection，不是偽造 Runner 事件。`scripts/verify-ledger-examples.py` 檢查區間／確定性、quantity·ms 和精確估價，沒有實作完整 event reducer。

| 案例 | 手算結果 |
|---|---|
| Active 2 CPU 1 秒，Idle 0.5 CPU 2 秒 | 3,000,000 milliCPU·ms |
| cold Suspend，compute 在 1 秒確認停止，volume 1024 bytes 留到 3 秒 | compute 1,000,000；volume 3,072,000 byte·ms |
| snapshot 2048 bytes，TTL 2 秒到期但 3 秒確認刪除 | 6,144,000 byte·ms |
| Lost：H=1 秒、恢復=3 秒 | 已確認 1,000,000，另 2 秒 uncertain；可信 stop=2 秒補件後確定總量 2,000,000 |
| UTC 9 月底前後各 1 秒，1 CPU | 9 月、10 月各 1,000,000 |
| 費率在第 1 秒改版：每 CPU 秒 1 cent → 2 cents | 2 秒共 3 cents；中間切段不能用新率覆蓋舊率 |
| Active 同狀態從 1 CPU 改成 2 CPU，各 1 秒 | 3,000,000 |
| 兩段各值 0.5 cent | 同 line 合計 1 cent，不能每段 round 成 2 cents |

後續 #11/#17/#25 另驗：重送一次只產生一次 projection；同 ID 異 payload 拒絕；事件亂序／sequence 缺口不結帳；舊 generation 不影響當前狀態；月結後 late correction 留差額軌跡。這些尚未有 runtime／DB 實測。

執行：`python3 scripts/verify-ledger-examples.py`。這個純標準函式庫工具可在 macOS/Linux 離線跑，不呼叫供應商 API、不產生帳單。
