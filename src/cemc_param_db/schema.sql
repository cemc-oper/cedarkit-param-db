-- ============================================================
-- GRIB2 要素注册表数据库（SQLite）
-- 对应 reki/reki/readers/grib/config/param_registry_spec.md v1.1 的数据模型
--
-- 数据库是"编辑真源"，param_registry.yaml 是由本库导出的"发布快照"。
-- 约束分工：
--   本库硬约束（UNIQUE/CHECK）：U1、U2、C4、E1/E3 的非空部分
--   YAML 校验层软约束（JSON Schema + pytest）：C1 白名单、C2 成对、
--   C3 instant 禁带时间窗、U4 全局冲突、L1-L3
-- ============================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------
-- 条目：一个 GRIB2 要素（编号三元组唯一确定）
-- ----------------------------------------------------------
CREATE TABLE entries (
    id             INTEGER PRIMARY KEY,

    -- key 三元组（spec §3.2, K1-K3）
    discipline     INTEGER NOT NULL CHECK (discipline BETWEEN 0 AND 255),
    category       INTEGER NOT NULL CHECK (category   BETWEEN 0 AND 255),
    number         INTEGER NOT NULL CHECK (number     BETWEEN 0 AND 255),

    -- 命名（spec §3.1）
    name           TEXT NOT NULL CHECK (length(trim(name)) > 0),  -- 通用名，CEMC 优先
    wgrib2_name    TEXT CHECK (wgrib2_name IS NULL OR length(trim(wgrib2_name)) > 0),

    -- 元数据（E3：不需要时存 NULL，不存空串）
    unit           TEXT CHECK (unit IS NULL OR length(unit) > 0),
    description    TEXT,
    description_cn TEXT,

    -- 信息性字段（E5，不参与 when 匹配）
    type_of_level  TEXT,
    level          REAL,

    -- 维护信息
    remark         TEXT,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),

    -- U1：三元组全局唯一
    UNIQUE (discipline, category, number)
);

-- ----------------------------------------------------------
-- 条件变体：spec §3.3，when 用 JSON 列承载
-- ----------------------------------------------------------
CREATE TABLE variants (
    id           INTEGER PRIMARY KEY,
    entry_id     INTEGER NOT NULL REFERENCES entries(id) ON DELETE CASCADE,

    name         TEXT NOT NULL CHECK (length(trim(name)) > 0),

    -- when 条件，规范化 JSON object（键排序、紧凑分隔符），
    -- 键属于 spec §3.4 白名单，值保留原生 int/float/str 类型。
    -- 例：{"first_level":10,"first_level_type":103,"stepType":"max"}
    when_json    TEXT NOT NULL CHECK (
                     json_valid(when_json)
                     AND json_type(when_json) = 'object'
                     AND length(when_json) > 2          -- 非空 map（V2）
                 ),

    -- 信息性字段（V4）
    type_of_level TEXT,
    level         REAL,

    -- 变体级元数据（spec §3.3：缺省存 NULL，导出时省略即"继承条目级"）
    unit           TEXT CHECK (unit IS NULL OR length(unit) > 0),
    description    TEXT,
    description_cn TEXT,

    -- params 列表顺序：spec §5 第 3 条"并列靠后"依赖它，导出必须按此排序
    sort_order   INTEGER NOT NULL,

    -- U2：同条目内变体名不重复
    UNIQUE (entry_id, name),
    -- C4：同条目内 when 不允许完全相同（依赖 when_json 写入前规范化）
    UNIQUE (entry_id, when_json)
);

CREATE INDEX idx_variants_entry ON variants (entry_id, sort_order);

-- ----------------------------------------------------------
-- 别名：条目级与变体级统一存放（U4 的条内部分）
-- ----------------------------------------------------------
CREATE TABLE aliases (
    id         INTEGER PRIMARY KEY,
    owner_type TEXT NOT NULL CHECK (owner_type IN ('entry', 'variant')),
    owner_id   INTEGER NOT NULL,        -- entries.id 或 variants.id（owner_type 区分）
    alias      TEXT NOT NULL CHECK (length(trim(alias)) > 0),

    UNIQUE (owner_type, owner_id, alias)
);

CREATE INDEX idx_aliases_alias ON aliases (alias);

-- ----------------------------------------------------------
-- 变更履历（预留）：记录谁在什么时候改了什么
-- ----------------------------------------------------------
CREATE TABLE change_log (
    id         INTEGER PRIMARY KEY,
    table_name TEXT NOT NULL,
    row_id     INTEGER NOT NULL,
    action     TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    detail     TEXT,                    -- JSON：变更前后内容
    changed_by TEXT,
    changed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
