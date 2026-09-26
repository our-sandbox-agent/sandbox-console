# #8 第一包：無 key 實測完成，PID 限制仍有阻塞

專用 Hyper-V Linux VM 已能執行固定診斷 image。本輪 shell、公開 repo／npm 工作負載、PTY、CPU、memory 的必要觀測通過；**E09 的 64 PID cap 會使 runsc sandbox 退出，不能 go**。E05 與 E10 未跑，不涉及任何 Claude 模型請求或費用。#8 保持 open，#10／#11 繼續等待。

這份結果只對下列環境成立，不推論其他 runsc 版本、平台或 PID 配額。沒有以 runc 取代 runsc、沒有以 root 跑測試程序。root 僅用於 VM 上 Docker 管理與讀取 host cgroup。

## 本輪環境與可追溯材料

| 項目 | 固定值／本輪觀測 |
|---|---|
| Host | Ubuntu 24.04.5 LTS amd64，Hyper-V 4 vCPU／8 GiB RAM |
| Kernel | 6.8.0-142-generic |
| Docker／runsc | 29.8.1／release-20260921.0 |
| Platform／cgroup | systrap／v2 systemd |
| Node／Claude | 22.23.3／2.1.283 |
| git／tmux | 2.39.5／3.3a |
| Image | `sha256:1728145d39d1e09111580fcd3a8a4931d0d0ebc0429caeb16ff295c86108e5cf` |
| Image recipe | commit `1711b8d`；[Dockerfile](../../diagnostics/gvisor/Dockerfile) 與 npm lockfile |
| 模型／憑證 | 無配置、無模型呼叫；CLI 只執行 `--version` |

表格只整理 **final run**。完整 run ID／起迄時間見 [report.json](evidence/2026-09-27-no-key/report.json)。UTC 日期為 2026-09-26，台北當地日期為 2026-09-27。

[environment.json](evidence/2026-09-27-no-key/environment.json)、[結束版本](evidence/2026-09-27-no-key/environment-end.json)、[preflight](evidence/2026-09-27-no-key/preflight.json)、[build log](evidence/2026-09-27-no-key/build.log)、[來源 hash](evidence/2026-09-27-no-key/source-manifest.json)。setup.jsonl 另含完整 dpkg 版本與 Node／Claude binary hash。起訖 kernel／Docker／runsc／Claude／image pin 一致；apt hold 不取代這個核對。

## 實測結果

| Case | 結果 | 代表證據與實際意義 |
|---|---|---|
| E01 runtime | pass | Docker Runtime=runsc；host 程序為 runsc-sandbox，實際 cmdline 含 systrap；核對 daemon flags |
| E02 shell | pass | UID/GID 1000，輸出 SHELL_OK，exit 0 |
| E03 repo | pass | clone 公開 sandbox-console fixture，checkout `02dc635`，記錄 lockfile 與測試檔 hash |
| E04 package | pass | `npm ci --ignore-scripts` 與 fixture 的 15 個 node tests 通過；完整 TAP 見 E04.jsonl |
| E05 Claude marker | not_run | 等專用 key／模型／預算；CLI version 成功不等於模型任務成功 |
| E06 PTY | pass | Alpine 非 root ptmx 最小／加強限制兩組均 exit 0；tmux resize、Ctrl-C、detach／reattach、強制中斷 client 後重連均有觀測 |
| E07 CPU | pass | 0.5 CPU cap，20.082 秒內實測比率 0.499877，200 個 throttled periods；預定容差 0.35–0.65 |
| E08 memory | pass | 128 MiB cap，逐批配置至 104 MiB 後容器 OOMKilled=true、container exit 137；host available 最低 7128 MiB |
| E09 PID | **fail** | runsc sandbox exit 2、Docker exec exit 128／WaitPID EOF；runc 對照能回 EAGAIN 並清理 child |
| E10 cold/session | not_run | 留待 Claude session／缺 key／重新注入的完整驗證；未用一般檔案測試冒充整列通過 |

E06 的外層 terminal resize 為 40×100，tmux 使用一行 status bar，pane `stty size` 實際為 39×100。工作 PID 107 在 detach、重新 attach、強制 kill Docker client、再次 attach 後均保留；tick 由 5 → 10 → 15 → 20 → 26，最後收到 Ctrl-C 並留下 SIGINT_RECEIVED。[原始 PTY 記錄](evidence/2026-09-27-no-key/E06.jsonl)

E08 的 host cgroup `memory.current/events` 已取樣；因 sandbox 在 OOM 時快速退出、cgroup 隨即消失，50 ms 樣本**沒有捕捉到 oom_kill counter 的增加**。結論依 memory.max、配置進度、Docker OOMKilled=true／exit 137，以及 host headroom 判定；不把 counter=0 寫成觀測到 event。[memory 原始記錄](evidence/2026-09-27-no-key/E08.jsonl)、[cgroup 樣本](evidence/2026-09-27-no-key/E08-cgroup.json)

## E09：host task cap 不能直接視為 guest PID 配額

同一診斷 image、UID 1000、64 PID cap、1 CPU、1 GiB memory，probe 最多 fork 80 個 child，無遞迴 fork。

| 觀測 | runsc | runc 診斷對照 |
|---|---|---|
| host pids.max | 64 | 64 |
| 50 ms 取樣 host task peak | 63 | 64 |
| guest 正常結果 | 未取得；probe 中途失去 sandbox | 62 個 child 後 errno 11 / EAGAIN |
| probe／container exit | 128／2，非 OOM | 0／container 仍 running |
| child 正常 wait/cleanup marker | 未取得 | CHILDREN_REAPED |

runsc 在 fork 期間整個 sandbox 退出，沒有達成「拒絕新程序而繼續正常運作」。host task 取樣可能漏掉瞬間峰值，不能從 63 推論 cap 沒生效，也不能推算 guest 已建多少個 PID。daemon／VM 留存，最終依 manifest 清除所有本輪容器。

[E09 原始命令與輸出](evidence/2026-09-27-no-key/E09.jsonl)、[runsc cgroup](evidence/2026-09-27-no-key/E09-runsc-cgroup.json)、[runc cgroup](evidence/2026-09-27-no-key/E09-runc-cgroup.json)。這足以阻擋目前設定的 go，但尚未斷言上游根因。下一個有界實驗應分離 runtime 所需 host thread headroom 與 guest 程序配額，再判斷版本／設定／實作方案；不能只是調高配額就宣称同一測試通過。

初輪觀測器假設 PID probe 必有 JSON，遇到 sandbox 提前退出只記到 StopIteration。已修正為保存缺失結果、container state 和 runc 對照；final run 用修正後的完整觀測器重新執行，不把解析失敗當 runtime 通過。前期 debug runs 留在本機，不混入此 report 的數值。

## 清理、完整性與下一步

[cleanup.jsonl](evidence/2026-09-27-no-key/cleanup.jsonl) 與 [manifest.json](evidence/2026-09-27-no-key/manifest.json) 記錄每個容器 ID／label 的核對和刪除，最終 label 查詢為空。本輪沒建立 volume，也沒掛載 host 資料或 Docker socket。診斷 image、build cache 與 evidence 保留供重跑。

```sh
python3 scripts/gvisor-report.py --check \
  docs/research/evidence/2026-09-27-no-key/report.json
```

預期 exit 2，`incomplete`：只剩 E05／E10 未執行；E09 仍明確 fail。所有引用 evidence 的 SHA-256 已核對，`runtime_go` 永遠為 false。這個工具檢查材料完整性，不會替代人工核對失敗或宣告 go。

後續先釐清 E09 的可接受程序限制方案，再待使用者提供專用 key 的配置位置、模型及預算／停止門檻，完成 E05／E10 與必要重測。參考 [可重跑流程](../../diagnostics/gvisor/README.md)。保持 #8 open、#10／#11 等待；本 PR 只用 Refs #8。
