[README.md](https://github.com/user-attachments/files/29704163/README.md)
# FlowSentinel

FlowSentinel es un motor asíncrono de alto rendimiento en Python diseñado para monitorear el mempool y la liquidez multi-venue en tiempo real. Su objetivo es detectar patrones de extracción de valor (MEV) y generar alertas explicables impulsadas por inteligencia artificial.

> [!NOTE]
> **Aviso de Observación:** Este sistema es puramente observacional y de alerta. **NUNCA** firma transacciones, **NUNCA** ejecuta operaciones financieras y **NUNCA** gestiona claves privadas de billeteras (wallets).

---

## Arquitectura de FlowSentinel

El sistema está estructurado en tres capas independientes y concurrentes conectadas a través de colas asíncronas con límites de contrapresión (backpressure):

```mermaid
graph TD
    subgraph Capa 1: Ingesta (Feeds)
        MF[SimulatedMempoolFeed] --> |TxIntent| Q[Async Queue]
        LF[SimulatedLiquidityFeed] --> |PoolState| Q
        OF[Real/Stub Feeds] -.-> |OrderBookSnapshot| Q
    end

    subgraph Capa 2: Detección e Inteligencia Artificial
        Q --> SD[Sandwich Detector]
        Q --> LS[Liquidity Scorer]
        Q --> PM[Predictive Model]
        
        SD --> |AnomalyCandidate| RC[LLM Risk Classifier]
        LS --> |AnomalyCandidate| RC
        PM --> |AnomalyCandidate| RC
        
        RC --> |Assessment| NG[Narrative Generator]
    end

    subgraph Capa 3: Alertas y Observabilidad
        NG --> |Incident Report| PE[Pipeline Orchestrator]
        PE --> |Trace ID context| WS[Webhook Sink]
        PE --> |Trace ID context| TS[Telegram Sink]
        
        PE --> |Latency & Counts| PM_M[Prometheus Exporter]
        PE --> |Context log| SL[Structlog Tracing]
    end
    
    WS --> |POST| LTR[Local Test Receiver]
```

---

## Getting Started en 5 Minutos

Siga estos sencillos pasos para iniciar y probar FlowSentinel localmente:

### 1. Clonar el repositorio y levantar la infraestructura
Levante los servicios locales de Redis y TimescaleDB mediante Docker Compose:
```bash
docker compose -f docker-compose.full.yml up -d
```

### 2. Crear y activar el entorno virtual
Instale el paquete de manera local en modo editable junto con las dependencias de desarrollo:
```bash
python -m venv .venv
# En Windows:
.\.venv\Scripts\activate
# En Linux/macOS:
source .venv/bin/activate

pip install -e .[dev]
```

### 3. Ejecutar el script de verificación E2E (Demo)
El script de demostración inyectará deliberadamente 3 transacciones tipo sandwich y 1 caída de liquidez sintética, validará la detección, el análisis de LLM (usando fallback rule-based local) y la entrega del webhook:
```bash
python scripts/run_demo.py
```

Debería ver el siguiente resumen al finalizar exitosamente:
```text
=======================================================
4/4 anomalías detectadas, clasificadas y alertadas — OK
=======================================================
```

---

## Cómo Conectar Fuentes Reales

Para conectar FlowSentinel a flujos de datos reales (producción) en lugar de datos simulados:

1. **Reemplazar `SimulatedMempoolFeed` por un Adaptador Real:**
   Implemente la interfaz abstracta `Feed` para crear un `RealMempoolFeed` que se conecte a un nodo de Ethereum o BSC (por ejemplo, a través de WebSockets con un proveedor como Alchemy, Infura o QuickNode).
2. **Configuración y Credenciales:**
   Agregue credenciales y direcciones URL de los nodos de RPC en el archivo `.env`.
3. **Mapeo de Datos:**
   Mapee la carga útil JSON-RPC entrante del mempool (suscripción `newPendingTransactions` o similar) para construir y validar el modelo Pydantic `TxIntent`.

---

## Despliegue en la Nube (Tiers Gratuitos)

FlowSentinel está diseñado para operar en infraestructuras distribuidas y puede ser desplegado de manera gratuita:

- **App & Webhook Receiver (FastAPI):** Se puede desplegar de forma gratuita en [Render](https://render.com/) o [Railway](https://railway.app/).
- **Redis Cache (Deduplicación):** Se puede utilizar el tier gratuito de [Upstash Redis](https://upstash.com/).
- **TimescaleDB (Base de datos de series temporales):** Se puede utilizar la base de datos PostgreSQL Serverless gratuita de [Neon](https://neon.tech/) o [Supabase](https://supabase.com/).
