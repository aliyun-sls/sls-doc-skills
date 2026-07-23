# 脚本映射

## 数据采集
| 脚本 | 用途 |
|---|---|
| `devops_data_generator/main.py --mode single` | 执行单次数据采集周期 |
| `devops_data_generator/main.py --mode continuous` | 持续采集（默认间隔 300 秒）|

## 验证查询
| 脚本 | 用途 |
|---|---|
| `devops_data_generator/scripts/query_cms_devops.py` | 查询 CMS Workspace 中 devops 域实体 |
| `devops_data_generator/scripts/verify_devops_details.py` | 检查关键实体字段值 |
| `devops_data_generator/scripts/diagnose_cms_entity_store.py` | 诊断 Workspace / SLS 对齐问题 |

## UModel 上传
| 脚本 | 用途 |
|---|---|
| `umodel_uploader/umodel_batch_uploader.py` | 批量上传 EntitySet / EntitySetLink 定义 |

所有脚本通过 `--config` 参数读取配置目录。
