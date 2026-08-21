-- ============================================================================
-- 要素库修订：与《CMA天气模式数据 - 2026.06》清单比对结果
-- 日期：2026-08-21
-- 依据：data/doc/CMA天气模式数据 - 2026.06.docx（2026-08-21 更新版）
--       五个业务系统（CMA-GFS / CMA-MESO-3KM / CMA-TYM / CMA-GEPS / CMA-REPS）
--       GRIB2 产品要素清单
-- 执行方式：sqlite3 cemc_param.db < 本文件（整体在一个事务中）
-- 执行后记得重新导出：
--   python -m cemc_param_db export -o <reki>/reki/readers/grib/config/param_registry.yaml
--   python -m cemc_param_db export-json -o <cemc-param-web>/public/params.json
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- A. 单位修正
-- ----------------------------------------------------------------------------

-- A1. pwat (0,1,3) 整层可降水量：柱状积分量，四个系统清单均为 kg/m2，
--     库中 kg/kg 系笔误（与比湿混淆）。
UPDATE entries
SET unit = 'kg/m2', updated_at = datetime('now')
WHERE id = 18 AND discipline = 0 AND category = 1 AND number = 3
  AND unit = 'kg/kg';

-- A2. mpv1 (0,2,225) 湿位涡垂直分量：位涡单位为 K·m²/(s·kg)，
--     原值 m² 误置分母；1e-6 对应 PVU 量级。
UPDATE entries
SET unit = '1e-6.K.m2/(s.kg)', updated_at = datetime('now')
WHERE id = 60 AND discipline = 0 AND category = 2 AND number = 225
  AND unit = '1e-6.k/(m2.s.kg)';

-- A3. kidx (0,7,2) K指数：原值 'C' 易误读（库仑），
--     与 wgrib2 官方单位及 2026-08-21 版清单（K）统一为 'K'。
UPDATE entries
SET unit = 'K', updated_at = datetime('now')
WHERE id = 104 AND discipline = 0 AND category = 7 AND number = 2
  AND unit = 'C';

-- ----------------------------------------------------------------------------
-- B. 中文名修正
-- ----------------------------------------------------------------------------

-- B1. tvw (0,1,64) TCIWV：英文为 Total column integrated water vapor，
--     "总柱状比湿"有误，应为水汽。
UPDATE entries
SET description_cn = '总柱状水汽', updated_at = datetime('now')
WHERE id = 31 AND discipline = 0 AND category = 1 AND number = 64
  AND description_cn = '总柱状比湿';

-- B2. albedo (0,19,1) ALBDO：反照率（清单正确，库误作"反射率"）。
UPDATE entries
SET description_cn = '反照率', updated_at = datetime('now')
WHERE id = 121 AND discipline = 0 AND category = 19 AND number = 1
  AND description_cn = '反射率';

-- B3. w (0,2,9) DZDT：产品在等压面（first_level_type=100）输出，
--     "等高面"说法有误，清单作"垂直速度"。
UPDATE entries
SET description_cn = '垂直速度', updated_at = datetime('now')
WHERE id = 54 AND discipline = 0 AND category = 2 AND number = 9
  AND description_cn = '等高面垂直速度';

-- B3a. 同属 entry 54 的三个"最大垂直速度"变体同步去掉"等高面"，
--      与清单"输出间隔内最大垂直速度"（MESO/TYM）口径一致。
UPDATE variants SET description_cn = '1小时最大垂直速度'
WHERE id = 43 AND description_cn = '1小时等高面最大垂直速度';
UPDATE variants SET description_cn = '3小时最大垂直速度'
WHERE id = 44 AND description_cn = '3小时等高面最大垂直速度';
UPDATE variants SET description_cn = '最大垂直速度'
WHERE id = 45 AND description_cn = '等高面最大垂直速度';

-- B4. pc (0,1,228)：英文 Condensation layer pressure、单位 Pa，
--     是气压不是高度；清单作"抬升凝结高度处气压"。
UPDATE entries
SET description_cn = '抬升凝结高度处气压', updated_at = datetime('now')
WHERE id = 38 AND discipline = 0 AND category = 1 AND number = 228
  AND description_cn = '抬升凝结高度';

-- B5. sshf (2,0,24) HFLUX：通量类要素，"辐射"措辞不妥；清单作"地表感热通量"。
UPDATE entries
SET description_cn = '感热通量', updated_at = datetime('now')
WHERE id = 126 AND discipline = 2 AND category = 0 AND number = 24
  AND description_cn = '感热辐射';

-- B6. slhf (0,0,10) LHTFL：同上；清单作"地表潜热通量"。
UPDATE entries
SET description_cn = '潜热通量', updated_at = datetime('now')
WHERE id = 7 AND discipline = 0 AND category = 0 AND number = 10
  AND description_cn = '潜热辐射';

-- ----------------------------------------------------------------------------
-- C. 别名补充（清单使用的短名，库中同三元组用的是另一套 wgrib2 名）
-- ----------------------------------------------------------------------------

-- C1. qc (0,1,22) 云水混合比：清单（GFS/MESO/TYM）用 CLWMR，库中 wgrib2_name=CLMR。
INSERT INTO aliases (owner_type, owner_id, alias)
VALUES ('entry', 24, 'CLWMR');

-- C2. sweatidx (0,7,5) 强天气胁迫指数：清单（GFS）用 SWEATX，库中 wgrib2_name=SX。
INSERT INTO aliases (owner_type, owner_id, alias)
VALUES ('entry', 106, 'SWEATX');

-- ----------------------------------------------------------------------------
-- D. 变更履历（change_log 为手工写入机制，此处逐条登记）
-- ----------------------------------------------------------------------------
INSERT INTO change_log (table_name, row_id, action, detail, changed_by) VALUES
 ('entries',  18, 'update', '{"unit": {"before": "kg/kg", "after": "kg/m2"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries',  60, 'update', '{"unit": {"before": "1e-6.k/(m2.s.kg)", "after": "1e-6.K.m2/(s.kg)"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries', 104, 'update', '{"unit": {"before": "C", "after": "K"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries',  31, 'update', '{"description_cn": {"before": "总柱状比湿", "after": "总柱状水汽"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries', 121, 'update', '{"description_cn": {"before": "反射率", "after": "反照率"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries',  54, 'update', '{"description_cn": {"before": "等高面垂直速度", "after": "垂直速度"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('variants', 43, 'update', '{"description_cn": {"before": "1小时等高面最大垂直速度", "after": "1小时最大垂直速度"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('variants', 44, 'update', '{"description_cn": {"before": "3小时等高面最大垂直速度", "after": "3小时最大垂直速度"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('variants', 45, 'update', '{"description_cn": {"before": "等高面最大垂直速度", "after": "最大垂直速度"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries',  38, 'update', '{"description_cn": {"before": "抬升凝结高度", "after": "抬升凝结高度处气压"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries', 126, 'update', '{"description_cn": {"before": "感热辐射", "after": "感热通量"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('entries',   7, 'update', '{"description_cn": {"before": "潜热辐射", "after": "潜热通量"}, "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('aliases',  (SELECT id FROM aliases WHERE owner_type='entry' AND owner_id=24  AND alias='CLWMR'),  'insert', '{"owner_type": "entry", "owner_id": 24, "alias": "CLWMR", "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp'),
 ('aliases',  (SELECT id FROM aliases WHERE owner_type='entry' AND owner_id=106 AND alias='SWEATX'), 'insert', '{"owner_type": "entry", "owner_id": 106, "alias": "SWEATX", "source": "CMA天气模式数据-2026.06 比对"}', 'wangdp');

COMMIT;

-- ============================================================================
-- 以下事项本次【不修改】，仅记录待办：
--
-- 1. sshf(2,0,24)/slhf(0,0,10) 单位 'ws/m2' 与库内辐射类 'w/m2' 约定不一致：
--    需先确认产品文件中存的是瞬时通量(W/m2)还是累积量(J/m2)，再决定是否改单位。
-- 2. tadv(0,0,224)/voradv(0,2,224)/qflx(0,1,224)/qdiv(0,1,225) 单位带存储
--    缩放因子（如 '1.e-6 k/s'），清单只写物理单位（K/s）：属既定本地约定，
--    建议后续在 remark 中注明"存储值 = 物理值 × 10^n"，不改 unit 值。
-- 3. GEPS/REPS 清单 2026-08-21 更新后已与库完全对齐，无对应修订。
-- 4. 清单文档侧笔误（反馈给文档维护方，与库无关）：
--    - GFS: HPBL 边界层高度单位 "W m-2 s" 应为 m
--    - GFS: 等高面 u/v 风单位 "m" 应为 m/s
--    - 辐射类单位 "W m-2 s" / "W/m**2" 全文写法不统一
-- ============================================================================
