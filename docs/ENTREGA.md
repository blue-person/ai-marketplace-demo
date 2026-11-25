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

La cuenta `platform@marketplace.test` (rol `system`) recibe el 20 % de cada ejecución. No inicia sesión y no se puede suspender. La semilla crea tres ejecuciones terminadas, una pagada de `company1` a un agente de `dev1`, una fallida y reembolsada de `company2` y una gratuita de `dev1` con su propio agente. Los saldos y los montos del libro usan cuatro decimales.

Las API keys de las cuentas activas se imprimen una sola vez en el log del servicio `seed`, con `docker compose logs seed`.

La semilla también crea cinco agentes de ejemplo para recorrer el catálogo. `dev1` tiene dos aprobados (Text Summarizer y Code Reviewer) y uno rechazado (Data Cleaner), y `dev2` tiene uno aprobado (Support Assistant) y uno pendiente (Market Researcher) que un administrador puede revisar en la pestaña Agents del panel.

## Estado de los módulos

| Módulo | Estado (completo / parcial / no implementado) | Observaciones |
|---|---|---|
| Registro y verificación (20 %) | completo | Registro con perfil y código de referido, aprobación o rechazo por un administrador, aprobación de los perfiles completos por el robot C++, API key enviada por correo con solo su hash guardado, bono de 5 USD al referidor y suspensión o reactivación de cuentas. |
| Transferencias de crédito (10 %) | completo | Transferencias atómicas entre developers y companies, con bloqueo de filas en orden fijo y libro de movimientos. |
| Catálogo de agentes (10 %) | completo | Los developers publican agentes con nombre, descripción, precio por ejecución, categoría, endpoint de prueba y modelo. Cada agente queda pendiente hasta que un administrador lo aprueba o lo rechaza con un motivo de una lista, y solo los aprobados aparecen en el catálogo, al que acceden las cuentas con sesión. El endpoint de prueba se guarda y se valida, pero el backend no lo invoca, y solo lo ven el dueño y los administradores. |
| Ejecución de agentes (30 %) | completo | Developers y companies ejecutan agentes aprobados desde la página Executions o con su API key. La cabecera `Idempotency-Key` es obligatoria y evita cobrar dos veces. El precio se cobra primero, el modelo se llama fuera de la transacción y el pago (80 % al developer y 20 % a la cuenta de la plataforma) ocurre solo si el modelo responde. Si falla, el precio vuelve al usuario con un movimiento nuevo del libro. Un developer ejecuta sus propios agentes sin costo. El historial guarda el prompt (hasta 2000 caracteres) y la respuesta (hasta 4000). El usuario ve todo lo suyo, el developer ve agente, costo y ganancia sin el texto y el administrador ve solo montos. |
| Ejecuciones programadas (30 %) | no implementado | |
| Registro de auditoría (adicional) | completo | Registra quién hizo qué, cuándo y sobre quién, con los valores anteriores y nuevos. El administrador lo consulta en la pestaña Audit log. |

## Limitaciones conocidas

El módulo de ejecuciones programadas todavía no está implementado.
