"""cedarkit-param-db：GRIB2 要素注册表的 SQLite 编辑真源。

数据库是唯一手工编辑入口；``param_registry.yaml``（reki 包内）是由本库
导出的发布快照，禁止手工修改。

典型流程::

    python -m cedarkit_param_db init                     # 建库
    python -m cedarkit_param_db import --yaml <注册表>    # 灌入（全量替换）
    # ... 用 SQL 编辑数据库 ...
    python -m cedarkit_param_db export -o <注册表>        # 导出快照
    python -m cedarkit_param_db check --yaml <注册表>     # CI drift 检查
"""

from cedarkit_param_db.db import DEFAULT_DB_PATH, connect, init_db
from cedarkit_param_db.exporter import export_entries, export_text
from cedarkit_param_db.importer import import_registry

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_DB_PATH",
    "connect",
    "init_db",
    "export_entries",
    "export_text",
    "import_registry",
    "__version__",
]
