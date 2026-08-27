-- Semantic-preserving namespace migration approved after T2-01.
UPDATE entries SET parameter_id = 'cedarkit.' || substr(parameter_id, 6)
WHERE parameter_id GLOB 'cemc.*';
UPDATE variants SET parameter_id = 'cedarkit.' || substr(parameter_id, 6)
WHERE parameter_id GLOB 'cemc.*';
UPDATE parameter_id_tombstones SET parameter_id = 'cedarkit.' || substr(parameter_id, 6)
WHERE parameter_id GLOB 'cemc.*';
