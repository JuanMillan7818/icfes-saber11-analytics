SELECT
    ano,
    periodo,
    AVG(CAST(punt_global AS DOUBLE))                 AS promedio_global,
    AVG(CAST(punt_matematicas AS DOUBLE))            AS promedio_matematicas,
    AVG(CAST(punt_lectura_critica AS DOUBLE))        AS promedio_lectura,
    AVG(CAST(punt_c_naturales AS DOUBLE))            AS promedio_ciencias,
    AVG(CAST(punt_sociales_ciudadanas AS DOUBLE))    AS promedio_sociales,
    AVG(CAST(punt_ingles AS DOUBLE))                 AS promedio_ingles,
    COUNT(*)                                         AS total_estudiantes
FROM read_parquet('./files/parquet/*.parquet')
GROUP BY ano, periodo
ORDER BY ano, periodo
