# Ficha de entrega

> Diligencie esta ficha antes de generar el ZIP con `scripts/package.py`.
> El grupo auditor la usará para levantar y probar su aplicación.

## Datos del grupo

- **Grupo:** <!-- p. ej. grupo03 -->
- **Integrantes:** Alejandro Buelvas García y John Alexander Pinto Ramos
- **Caso:** marketplace
- **Versión entregada:** <!-- commit o etiqueta, si usan git -->
- **Fecha:** <!-- AAAA-MM-DD -->

## Cómo levantar la aplicación

Se siguen estos pasos en orden, desde una terminal.

1. Entre a la carpeta del proyecto con `cd ai-marketplace-demo`.
2. Cree el archivo de configuración con `cp .env.example .env`.
3. Abra `.env` y cambie cada valor `change-me` por un secreto propio.
4. Construya y levante todos los servicios con `docker compose up --build`.
5. Cuando termine la construcción, abra `http://localhost:8080` para usar la aplicación y `http://localhost:8025` para ver los correos que envía.

Para volver a empezar con la base de datos limpia, se ejecuta `docker compose down -v` y luego el paso 4.

## Cuentas de prueba

Todas usan la contraseña `SEED_PASSWORD` del `.env`, salvo el administrador, que usa `ADMIN_PASSWORD`. Incluya al menos dos cuentas por rol.

| Rol | Correo | Datos semilla asociados |
|---|---|---|
| admin | (valor de `ADMIN_EMAIL`) | |
| | | |
| | | |

## Estado de los módulos

| Módulo | Estado (completo / parcial / no implementado) | Observaciones |
|---|---|---|
| | | |

## Limitaciones conocidas

<!-- Lo que saben que no funciona o que quedó pendiente. -->
