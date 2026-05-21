SELECT
    ano,
    cole_depto_ubicacion                             AS depto,
    AVG(CAST(punt_global AS DOUBLE))                 AS promedio_global,
    AVG(CAST(punt_matematicas AS DOUBLE))            AS promedio_matematicas,
    AVG(CAST(punt_lectura_critica AS DOUBLE))        AS promedio_lectura,
    AVG(CAST(punt_c_naturales AS DOUBLE))            AS promedio_ciencias,
    AVG(CAST(punt_sociales_ciudadanas AS DOUBLE))    AS promedio_sociales,
    COUNT(*)                                         AS total_estudiantes
FROM read_parquet('./files/parquet/*.parquet')
WHERE cole_depto_ubicacion IS NOT NULL
GROUP BY ano, cole_depto_ubicacion
ORDER BY ano, promedio_global DESC
