# cedarkit-param-db

CedarKit GRIB2 要素注册表的**编辑真源**（SQLite 实现）。

定位：reki 包内的 `reki/readers/grib/config/param_registry.yaml` 是运行时消费的
**发布快照**（随 reki 版本固化、离线可用、diff 可 review），本数据库是它的上游。
数据流向严格单向：

```
cedarkit_param.db ──export──────> param_registry.yaml ──打包──> reki wheel（只读）
             └─export-json──> params.json ──────────────> cedarkit-param-web/public/（公开展示站点）
```

禁止手工编辑 YAML 快照；所有要素维护通过 SQL 修改数据库后重新导出。

数据模型与约束规则见 reki 仓库的 `param_registry_spec.md`（v1.1）。
schema 与其字段一一对应，约束分工：

| 规则 | 落点 |
|---|---|
| U1 三元组唯一 / U2 条内变体名唯一 / C4 条内 when 唯一 | 数据库 UNIQUE 约束（硬保证） |
| E1/E3 非空、禁空串 | 数据库 CHECK（硬保证） |
| C1 when 键白名单 / C2 second_level 成对 / C3 instant 禁带时间窗 | YAML 校验层（reki `tests/readers/grib/test_param_registry.py`） |
| U4 别名冲突 / N1-N2 命名 / L1-L3 展示 | YAML 校验层（数据库仅保证条内别名不重复） |

`when` 条件存为规范化 JSON 文本列（键排序、紧凑分隔符），C4 唯一索引因此
不受键序/空白影响；导出时恢复为 spec §3.4 白名单的书写顺序。

## 项目结构

```
cedarkit-param-db/
├── pyproject.toml
├── README.md
├── cedarkit_param.db              # 数据库文件（init 生成，可纳入版本管理；.gitattributes 已标记为 binary）
├── src/cedarkit_param_db/
│   ├── schema.sql             -- 建库 DDL
│   ├── db.py                  -- 连接与初始化
│   ├── importer.py            -- YAML → DB（全量替换）
│   ├── exporter.py            -- DB → YAML / params.json（确定性导出）
│   └── __main__.py            -- CLI
└── tests/
    ├── test_roundtrip.py
    └── test_export_json.py
```

## 使用

```bash
pip install -e .            # 或 uv pip install -e .

# 建库（首次）
python -m cedarkit_param_db init

# 从现有注册表灌入（全量替换）
python -m cedarkit_param_db import \
  --yaml ../../repo/reki/reki/readers/grib/config/param_registry.yaml

# 日常维护：用任意 SQLite 客户端/SQL 修改 cedarkit_param.db
sqlite3 cedarkit_param.db
sqlite> UPDATE variants SET name = '...' WHERE ...;

# 导出 YAML 快照（覆盖 reki 包内文件）
python -m cedarkit_param_db export \
  -o ../../repo/reki/reki/readers/grib/config/param_registry.yaml

# 导出 params.json（cedarkit-param-web 公开展示端的数据契约）
python -m cedarkit_param_db export-json -o ../cedarkit-param-web/public/params.json

# CI drift 检查：快照与数据库不一致时退出码为 1 并输出 diff（--yaml/--json 可单独或同时使用）
python -m cedarkit_param_db check \
  --yaml ../../repo/reki/reki/readers/grib/config/param_registry.yaml \
  --json ../cedarkit-param-web/public/params.json
```

导出后别忘了跑 reki 侧的校验测试（JSON Schema + U/C/N/L 规则）：

```bash
cd ../../repo/reki && pytest tests/readers/grib -v
```

## params.json 导出（公开展示端）

`params.json` 是与 YAML 快照平级的第二种导出物，供公开展示端
[cedarkit-param-web](../cedarkit-param-web/) 构建要素清单静态站点。它是两个项目之间的
**契约文件**：只含规范化原始数据（entries/variants/aliases/remark/updated_at，
when 按 spec 语义顺序），不含展示层预加工字段；`meta.schema_version` 是两边
升级的协调点，契约变更必须递增版本号。

导出是确定性的（字段顺序、缩进、末尾换行固定），提交到 cedarkit-param-web 仓库后
PR diff 即可读，充当发布前的内容审批。

## 设计要点

- **sort_order 列**：spec §5"并列靠后"裁决依赖 `params` 书写顺序，数据库表
  本身无序，必须显式记录，导出按它排序。
- **浮点层次值**：`level` 列是 REAL，导出时整数值写回整数形式（`2` 而非
  `2.0`），与历史快照格式保持一致；`when` 内的数值经 JSON 保留原生类型，
  不受影响。
- **变体级元数据继承**：`unit`/`description`/`description_cn` 为 NULL 表示
  继承条目级，导出时省略该字段。
- **change_log 表**：预留的变更履历，当前需手工或自行加触发器写入。
- **when_json 规范化**：写入必须经 `importer.canonicalize_when()`（或等价的
  键排序紧凑 JSON），否则 C4 唯一索引可能被绕过。

## 测试

```bash
pip install -e ".[test]"
pytest
```

roundtrip 测试以 reki 包内的注册表为基准：导入 → 导出 → 数据结构与原文
逐字节（头部注释除外）双重对比。
