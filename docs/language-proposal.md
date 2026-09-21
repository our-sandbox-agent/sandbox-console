# 語言配置提案

狀態：**提案，待確認團隊的 Go 維護能力**。追蹤 [#7](https://github.com/our-sandbox-agent/sandbox-console/issues/7)；這份文件不代表 Runner 已開工，也不關閉 #7 的其他契約工作。

## 建議配置

| 元件 | 建議 | 取捨 |
|---|---|---|
| 現有前端 | 維持 JavaScript | 不為語言統一而重寫已可用的原型。 |
| 控制平面 | TypeScript；沿用 Hono／Postgres 方向 | 與前端共享資料契約較方便，但仍需要執行期驗證、授權與持久化設計。 |
| Runner | 有 Go 維護能力時，第一版就用 Go | 可使用 Go SDK／系統工具庫；不要先交付 Node 版再預排重寫。 |
| CLI | Go | 可按目標 OS／架構發布執行檔；靜態連結、終端行為與安裝更新仍須實測。 |

若團隊目前只熟 TypeScript，Runner 保持 TypeScript 是可行替代，不強迫未來改寫。CLI 是否仍採 Go，或接受 Node 執行環境，需明確選擇；不能一面稱為全 TypeScript，一面承諾 Go 的發佈方式。

## 哪些判斷有依據

- gVisor 可透過 [Docker runtime](https://gvisor.dev/docs/user_guide/quick_start/docker/) 或 [OCI runtime](https://gvisor.dev/docs/user_guide/quick_start/oci/) 介面操作，上層 Runner 不必與底層使用相同語言。
- Firecracker 的 [Go SDK](https://github.com/firecracker-microvm/firecracker-go-sdk) 封裝其 API，README 也明確指出部分功能尚未涵蓋；[官方入門文件](https://github.com/firecracker-microvm/firecracker/blob/main/docs/getting-started.md) 展示 API 操作，因此 TypeScript 呼叫 API 也是可行路徑。
- Go 能降低部分介接成本是工程判斷，不是安全性或進度保證。是否可複用其他專案程式碼，還要檢查授權、架構耦合、版本與維護成本；不以「同語言」推導「可直接搬用」。
- Rust 不是唯一替代方案；目前不引入更多語言，是為了控制團隊維護成本。
- 「Go 起步多 3–4 天」「TypeScript 每階段多一週」尚無本專案實測，不能當排程承諾。

## 對原計劃的修訂方式

原詳細版第 1 步的 Node／Fastify／dockerode 暫時 Runner，以及第 3 步的 Go 重寫，是需要撤換的路線；**不再把重寫當必交里程碑**。語言定案後，同一個 PR 應同步修改下列內容：

1. 第 1 步 Runner 語言、套件、adapter 目錄與部署方式。
2. 第 3 步第 0 項改為接入既有 Runner；移除「先 Node 頂著、之後再改寫」退路。
3. 第 3 步套件表、風險與估時，改以接線／契約測試實際範圍估算，不直接扣除一週。
4. 第 4–8 步的 Go 程式例子、Firecracker SDK 與 CLI 發佈方式，依最終配置保持一致。
5. 短版與詳細版總估時重新校準；既有票的驗收邊界保持可追溯。

本提案未確認前，兩份原計劃的語言／重寫描述只作歷史設計參考，不據此建立暫時 Node Runner。

## 下一個可驗收切片

語言定案並完成 #7 必要契約後，由 #8 驗證既有 Linux 測試環境中的 gVisor 相容性。後續才進 Runner 建立／查詢／停止與檔案持久化；不先承諾暖恢復、不因選 Go 就啟用 Firecracker 或購買主機。

Runner 使用固定 adapter 邊界、明確 timeout／錯誤／清理規則與共用契約測試。CLI 和 Runner 可共用資料型別，但 CLI 仍經控制平面操作，不繞過授權邊界。

需確認的問題：**誰負責維護 Go？是否願意讓 Runner 與 CLI 從第一版採用 Go？** 其餘不因語言選擇而自動定案的產品契約，仍由 #7 追蹤。
