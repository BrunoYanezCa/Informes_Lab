# Informes de Laboratorio

Aplicación Streamlit para cargar libros Excel desde el navegador, editar un informe por muestra y descargar el PDF. La aplicación está pensada para desplegarse online; no ofrece selección de archivos mediante rutas locales.

## Despliegue online

1. Sube este proyecto a un repositorio privado de GitHub. No agregues libros de resultados, PDF de clientes ni archivos JSON de configuración con información confidencial.
2. En Streamlit Community Cloud, crea una aplicación desde ese repositorio y selecciona `app.py` como archivo principal.
3. Usa Python 3.11 o posterior e instala las dependencias de `requirements.txt`.
4. Comparte la URL únicamente con usuarios autorizados. Revisa las condiciones de privacidad y retención del proveedor de hosting antes de subir resultados de laboratorio.
5. En la aplicación, carga el libro `.xlsx` o `.xlsm` con el selector de archivos del navegador. La app lo procesa en la sesión de Streamlit, sin escribir el Excel ni el PDF en disco.

La firma y el logo incluidos en `assets/` se empaquetan con la aplicación. La firma de autorización es un recurso sensible: mantén privado el repositorio y restringe el acceso al despliegue.

## Catálogo de análisis

En la pestaña **Configuración** se editan los nombres, métodos/esquemas, analitos, unidades y límites L.D./L.C. por analito y unidad; para PAG se crean filas por cada analito y unidad del libro cargado. Los datos generales se guardan como valores predeterminados globales para cualquier muestra. Las fechas de ejecución por análisis se muestran para rectificación y también se guardan como defaults. El catálogo y las ediciones de la grilla se conservan en `config/user_preferences.json`, archivo local ignorado por Git. La firma activa se reemplaza permanentemente desde **Datos generales** y la firma previa se conserva en `assets/signature.original.jpeg`, que se puede restaurar desde la misma sección. Al restaurar las ediciones de resultados es necesario volver a cargar el mismo libro Excel; el libro no se guarda en el servidor. En servicios con almacenamiento efímero, las preferencias locales no sobreviven a la recreación de la instancia.

## Firma y emisión

En **Datos generales** se pueden editar nombre y cargo de quien firma, lugar de emisión y fecha. El PDF presenta la fecha en español, por ejemplo `16 de Noviembre del 2026`. La firma, nombre, cargo y fecha se imprimen sobre el pie institucional y debajo del contenido y las observaciones, en la última página.

## Pruebas

En una tarea de CI o entorno de desarrollo con los paquetes de `requirements.txt` instalados:

```powershell
python -m pytest -q
```

El PDF se genera en memoria con ReportLab. Las hojas se leen en modo de solo lectura y no se modifica el Excel de origen.

El informe mantiene una estructura fija: metodología, resultados generales y fechas de ejecución. Los resultados generales se muestran en una tabla simple; PAG se resume allí y sus analitos se detallan en una sección independiente, con una columna por cada unidad disponible (por ejemplo, `% Area` y `g/100g`) y agrupación por familia cuando la hoja fuente la informa.

La casilla **Generate report in English** cambia las etiquetas, secciones, leyendas y textos institucionales del informe; la selección queda guardada como preferencia. Las fechas se muestran en formato `DD/MM/AAAA` tanto en los datos generales como en ejecución.
