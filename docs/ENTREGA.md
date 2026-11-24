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
| admin | (valor de `ADMIN_EMAIL`) | Sin saldo. Ve las solicitudes, las cuentas y el registro de auditoría en el panel. |
| developer | dev1@marketplace.test | 100.00 USD de saldo inicial y una API key. Es quien refirió a la cuenta pendiente completa. |
| developer | dev2@marketplace.test | 100.00 USD de saldo inicial y una API key. |
| company | company1@marketplace.test | 100.00 USD de saldo inicial y una API key. |
| company | company2@marketplace.test | 100.00 USD de saldo inicial y una API key. |
| bot | approval.robot@marketplace.test | No inicia sesión. Usa la API key de `WORKER_API_KEY`. |
| company (pendiente) | pending.complete@marketplace.test | Perfil completo. El robot la aprueba en su primer ciclo y dev1 recibe 5.00 USD. |
| developer (pendiente) | pending.incomplete@marketplace.test | Sin perfil. Espera la decisión de un administrador. |

Las API keys de las cuentas activas se imprimen una sola vez en el log del servicio `seed`, con `docker compose logs seed`.

## Estado de los módulos

| Módulo | Estado (completo / parcial / no implementado) | Observaciones |
|---|---|---|
| Registro y verificación (20 %) | completo | Registro con perfil y código de referido, aprobación o rechazo por un administrador, aprobación de los perfiles completos por el robot C++, API key enviada por correo con solo su hash guardado, bono de 5 USD al referidor y suspensión o reactivación de cuentas. |
| Transferencias de crédito (10 %) | completo | Transferencias atómicas entre developers y companies, con bloqueo de filas en orden fijo y libro de movimientos. |
| Catálogo de agentes (10 %) | no implementado | |
| Ejecución de agentes (30 %) | no implementado | |
| Ejecuciones programadas (30 %) | no implementado | |
| Registro de auditoría (adicional) | completo | Registra quién hizo qué, cuándo y sobre quién, con los valores anteriores y nuevos. El administrador lo consulta en la pestaña Audit log. |

## Limitaciones conocidas

Los módulos de catálogo de agentes, ejecución de agentes y ejecuciones programadas todavía no están implementados.
