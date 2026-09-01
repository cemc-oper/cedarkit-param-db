-- M-06: publish the 50 M-05 confirmed CMADaaS mappings.
--
-- Evidence: doc/baseline/cmadaas-parameter-mapping/m05-evidence-ledger.json
-- Review basis: user-authorized CMADaaS small-region numerical comparisons,
-- reviewed on 2026-09-01.  This script deliberately excludes pending_review
-- and model_conflict records, including cedarkit.pwat.any -> PRE.
--
-- Preconditions are intentionally strict: this is a one-time migration from
-- the five stage-5 mappings.  Review this SQL source rather than SQLite bytes.
PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TEMP TABLE m06_expected (
    parameter_id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE
);

-- The original 146-code generic vocabulary did not list the following 27 CEMC
-- product elements.  Their names are recorded from the CEMC product tables;
-- the mappings below have the stronger, separate numerical-comparison proof.
CREATE TEMP TABLE m06_cemc_elements (
    code TEXT PRIMARY KEY,
    description_cn TEXT NOT NULL
);

INSERT INTO m06_cemc_elements(code, description_cn) VALUES
    ('ALBO', '地表反照率'),
    ('CAPE', '对流有效位能'),
    ('CIN', '对流抑制能'),
    ('CLCO', '云量'),
    ('CMRA', '云水混合比'),
    ('DCAPE', '下沉有效位能'),
    ('GRSP', '霰'),
    ('HIDX', '冰雹指数'),
    ('HT0', '0℃层高度'),
    ('IWMR', '冰水混合比'),
    ('PC', '抬升凝结高度'),
    ('PBLH', '边界层高度'),
    ('RACR', '雷达组合反射率'),
    ('RAR', '雷达反射率'),
    ('RHMAX', '最大相对湿度'),
    ('RHMIN', '最小相对湿度'),
    ('RMRA', '雨水混合比'),
    ('SHID', '沙氏指数'),
    ('SMRA', '雪水混合比'),
    ('SWID', '强天气胁迫指数'),
    ('TCCI', '总柱状云冰'),
    ('TCCW', '总柱状云水'),
    ('TIWV', '总柱状比湿（整层水汽含量）'),
    ('TOSN', '降雪量'),
    ('WIDX', '大风指数'),
    ('WSGU', '阵风风速'),
    ('ZNT', '粗糙度');

INSERT INTO external_elements(namespace, code, description_cn, source_ref)
SELECT 'cmadaas', code, description_cn,
       'doc/ref/cmadaas-cemc-data.md (CEMC product element tables; accessed 2026-09-01)'
FROM m06_cemc_elements;

INSERT INTO m06_expected(parameter_id, code) VALUES
    ('cedarkit.albedo.any', 'ALBO'),
    ('cedarkit.cape.any', 'CAPE'),
    ('cedarkit.cc', 'CLCO'),
    ('cedarkit.cdbz', 'RACR'),
    ('cedarkit.cin.any', 'CIN'),
    ('cedarkit.dbz', 'RAR'),
    ('cedarkit.dcape', 'DCAPE'),
    ('cedarkit.graupel', 'GRSP'),
    ('cedarkit.gust', 'WSGU'),
    ('cedarkit.h.any', 'GPH'),
    ('cedarkit.hcc', 'HCC'),
    ('cedarkit.hi.any', 'HIDX'),
    ('cedarkit.ht0.any', 'HT0'),
    ('cedarkit.kidx.any', 'KIDX'),
    ('cedarkit.lcc', 'LCC'),
    ('cedarkit.mcc', 'MCC'),
    ('cedarkit.pblh.any', 'PBLH'),
    ('cedarkit.pc.any', 'PC'),
    ('cedarkit.pli.any', 'PLI'),
    ('cedarkit.psl.any', 'SSP'),
    ('cedarkit.q', 'SHU'),
    ('cedarkit.qc', 'CMRA'),
    ('cedarkit.qdiv', 'MFVO'),
    ('cedarkit.qflx', 'MOFU'),
    ('cedarkit.qi', 'IWMR'),
    ('cedarkit.qr', 'RMRA'),
    ('cedarkit.qs', 'SMRA'),
    ('cedarkit.rainc.any', 'CPE'),
    ('cedarkit.rainnc.any', 'LPE'),
    ('cedarkit.rh', 'RHU'),
    ('cedarkit.rhmax', 'RHMAX'),
    ('cedarkit.rhmin', 'RHMIN'),
    ('cedarkit.sd.any', 'SDE'),
    ('cedarkit.sf.any', 'TOSN'),
    ('cedarkit.si.any', 'SHID'),
    ('cedarkit.sweatidx.any', 'SWID'),
    ('cedarkit.t', 'TEM'),
    ('cedarkit.tadv', 'TEAD'),
    ('cedarkit.tcc', 'TCC'),
    ('cedarkit.tcw.any', 'TCCW'),
    ('cedarkit.td', 'DPT'),
    ('cedarkit.theta-se', 'PPT'),
    ('cedarkit.tiw.any', 'TCCI'),
    ('cedarkit.ttd', 'DPD'),
    ('cedarkit.tvw.any', 'TIWV'),
    ('cedarkit.vis.any', 'VIS'),
    ('cedarkit.voradv', 'VOAD'),
    ('cedarkit.w.any', 'VVM'),
    ('cedarkit.wi.any', 'WIDX'),
    ('cedarkit.znt.any', 'ZNT');

-- CHECK makes an unmet precondition abort the whole transaction.  It verifies
-- all target entries/codes exist, only the two already-confirmed baseline
-- mappings are present, no target entry has a different code, and the stage-5
-- baseline still consists of exactly five CMADaaS mappings.
CREATE TEMP TABLE m06_guard (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO m06_guard(ok)
SELECT CASE WHEN
    (SELECT count(*) FROM m06_expected) = 50
    AND (SELECT count(*) FROM m06_cemc_elements) = 27
    AND (SELECT count(*) FROM entries e JOIN m06_expected x ON x.parameter_id = e.parameter_id) = 50
    AND (SELECT count(*) FROM external_elements v JOIN m06_expected x
         ON x.code = v.code WHERE v.namespace = 'cmadaas') = 50
    AND (SELECT count(*) FROM entry_external_elements m
         JOIN entries e ON e.id = m.entry_id
         JOIN m06_expected x ON x.parameter_id = e.parameter_id
         WHERE m.namespace = 'cmadaas' AND m.code = x.code) = 2
    AND NOT EXISTS (
        SELECT 1
        FROM entries e
        JOIN m06_expected x ON x.parameter_id = e.parameter_id
        JOIN entry_external_elements m ON m.entry_id = e.id AND m.namespace = 'cmadaas'
        WHERE m.code <> x.code
    )
    AND (SELECT count(*) FROM entry_external_elements WHERE namespace = 'cmadaas') = 5
THEN 1 ELSE 0 END;

INSERT INTO entry_external_elements(entry_id, namespace, code)
SELECT e.id, 'cmadaas', x.code
FROM m06_expected x
JOIN entries e ON e.parameter_id = x.parameter_id
LEFT JOIN entry_external_elements m ON m.entry_id = e.id AND m.namespace = 'cmadaas'
WHERE m.entry_id IS NULL;

-- Postconditions: 48 new rows plus the two pre-existing confirmed rows.
INSERT INTO m06_guard(ok)
SELECT CASE WHEN
    (SELECT count(*) FROM entry_external_elements WHERE namespace = 'cmadaas') = 53
    AND (SELECT count(*) FROM entries e
         JOIN m06_expected x ON x.parameter_id = e.parameter_id
         JOIN entry_external_elements m ON m.entry_id = e.id
         WHERE m.namespace = 'cmadaas' AND m.code = x.code) = 50
THEN 1 ELSE 0 END;

DROP TABLE m06_guard;
DROP TABLE m06_cemc_elements;
DROP TABLE m06_expected;
COMMIT;
PRAGMA foreign_key_check;
