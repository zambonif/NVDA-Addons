# Diario para NVDA

[English](README.md) · [Português do Brasil](README.pt-BR.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Français](README.fr.md)

Versión 1.3.0

Diario para NVDA es un diario personal accesible y sin conexión, integrado con el lector de pantalla NVDA. Su combinación distintiva reúne entradas con fecha elegida, registro automático de creación, una bóveda cifrada protegida por contraseña, recuperación opcional y corrección ortográfica accesible en tiempo real.

## Características principales

- Crear, listar, leer, editar y eliminar entradas.
- Elegir la fecha de cada entrada sin perder la fecha y hora originales de creación.
- Proteger títulos, fechas y texto en una bóveda con cifrado autenticado AES-256-GCM.
- Cambiar la contraseña y configurar opcionalmente una frase de recuperación.
- Oír un sonido al terminar una palabra posiblemente incorrecta sin perder el espacio, la puntuación o el salto de línea introducido.
- Abrir sugerencias con clic derecho, Aplicaciones, Shift+F10 o Alt+F10.
- Sustituir la palabra, ignorarla durante la sesión actual de NVDA o añadirla al diccionario local del Diario.
- Exportar los dos archivos cifrados de la bóveda a un ZIP e importar únicamente entradas que aún no existen en el Diario abierto.
- Usar la interfaz y la documentación en portugués de Brasil, inglés, español, italiano o francés.
- Mantener todos los datos en el equipo; el complemento no envía entradas a Internet.

## Requisitos

- NVDA 2025.1 o posterior.
- Windows 8 o posterior para la API nativa de corrección ortográfica. Las versiones actuales de NVDA requieren una versión de Windows más reciente y compatible.
- Un diccionario ortográfico de Windows para el idioma seleccionado en el Diario. Si no está disponible, el Diario continúa funcionando con normalidad y solo se desactiva el corrector para ese idioma.

## Instalación y apertura

Instala `diario-1.3.0.nvda-addon` desde la Tienda de complementos de NVDA o abre el paquete directamente y confirma la instalación. Reinicia NVDA cuando se solicite.

Abre el Diario desde menú de NVDA > Herramientas > Diario o pulsa NVDA+Alt+D. El gesto puede cambiarse en Gestos de entrada, dentro de la categoría Diario.

## Corrección ortográfica

Los campos de título y texto se comprueban mientras escribes. Después de una palabra seguida por espacio, puntuación, Tab o Enter, se reproduce un aviso si Windows la considera incorrecta. El separador siempre se introduce, por lo que puedes ignorar el aviso y seguir escribiendo.

Sitúa el cursor sobre la palabra o después de ella y pulsa Aplicaciones, Shift+F10 o Alt+F10. También puedes hacer clic derecho sobre la palabra. El menú accesible muestra hasta ocho sugerencias de Windows y luego:

- **Ignorar en esta sesión:** detiene los avisos para esa palabra hasta reiniciar NVDA.
- **Añadir al diccionario local:** guarda la palabra en `dicionario.txt`, dentro de la carpeta de datos del Diario, y evita futuros avisos.

El diccionario local es un archivo de texto UTF-8 que contiene únicamente las palabras añadidas por el usuario. No está cifrado porque no contiene entradas del diario. Los cinco idiomas de la interfaz comparten el mismo archivo.

## Exportación e importación de copias cifradas

Los botones **Exportar copia de seguridad** e **Importar copia de seguridad** solo están disponibles después de desbloquear el Diario.

**Exportar copia de seguridad** abre un diálogo para elegir dónde guardar y crea un ZIP que contiene exactamente `diario.enc` y `diario.backup.enc`. Ambos archivos permanecen cifrados; ningún título, fecha o texto de entrada se escribe sin cifrar.

**Importar copia de seguridad** abre un diálogo para seleccionar el archivo, valida las dos copias cifradas en una ubicación temporal y añade solo las entradas cuyos identificadores aún no existen en el Diario actual. Las entradas existentes nunca se sustituyen, aunque una entrada importada con el mismo identificador tenga contenido diferente. Se conservan las fechas, títulos, textos y horas de creación de las entradas nuevas.

Una copia exportada desde la misma bóveda se abre con la clave que ya conserva el Diario desbloqueado y no solicita otra contraseña. Una copia procedente de una bóveda creada por separado tiene otra clave aleatoria, aunque el texto de la contraseña sea el mismo; solo en ese caso el complemento solicita la contraseña de esa copia. Esto no cambia la contraseña del Diario actual. Después de la combinación, las entradas nuevas quedan protegidas por la bóveda actual.

Si el ZIP no es válido, la contraseña es incorrecta, se cancela la operación o no hay entradas nuevas, el Diario actual no se modifica.

## Datos, privacidad y recuperación

Los datos se guardan bajo la carpeta de configuración de NVDA, en la subcarpeta `diario`. La bóveda principal es `diario.enc` y su copia de seguridad cifrada es `diario.backup.enc`.

Todo el contenido, incluidos títulos y fechas, se protege con cifrado autenticado AES-256-GCM mediante Windows CNG. La clave de la bóveda se protege a partir de la contraseña con PBKDF2-HMAC-SHA256 y 600.000 iteraciones. La frase de recuperación, si se configura, protege por separado la misma clave aleatoria.

La frase de recuperación no revela la contraseña anterior; solo permite crear una nueva. Si se olvidan ambas, el complemento no puede recuperar las entradas. Usa secretos largos y difíciles de adivinar y conserva copias independientes de los archivos cifrados.

La versión 1.3.0 mantiene el formato de la bóveda cifrada compatible con la versión 1.1.0.

## Idioma de la interfaz

Abre menú de NVDA > Preferencias > Opciones > Diario para elegir Português (Brasil), Español, Italiano, Français o English sin cambiar el idioma general de NVDA. Las ventanas nuevas aplican la selección de inmediato. Reinicia NVDA para actualizar también el elemento de Herramientas, la categoría y la descripción del gesto.

## Compilación y pruebas

El repositorio usa únicamente la biblioteca estándar de Python:

```text
python build.py
python -m unittest discover -s tests -v
```

El build lee la versión de `manifest.ini` y crea `dist/diario-<versión>.nvda-addon`, excluyendo pruebas, cachés y archivos de desarrollo del instalable. La integración nativa debe recibir una prueba final en Windows con NVDA antes de publicar en la tienda.

Usa `python build.py --source` para crear también el ZIP del código fuente y las sumas de comprobación.

## Licencia y autor

Copyright © Fernando de Paula Zamboni.

Licencia GNU General Public License, versión 2 o posterior. Consulta [LICENSE.txt](LICENSE.txt).
