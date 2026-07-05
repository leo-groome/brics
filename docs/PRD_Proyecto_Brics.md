# **Proyecto Brics: Documento de Requisitos de Producto (PRD)**

## **1\. Objetivo Operativo y Filosofía (El Alma de Valta Operative)**

**Ingeniería de Liberación aplicada a la construcción.** Proyecto Brics es una herramienta construida bajo el principio de una compañía humana: devolverle el tiempo y la libertad operativa al contratista (Cliente Cero Absoluto: la constructora del padre de Filis). El objetivo es destruir el "infierno de las hojas de cálculo" y reducir un ciclo de presupuestación de días a menos de una hora.

## **2\. La Visión (North Star)**

Brics evolucionará hasta convertirse en un orquestador autónomo de costos a nivel nacional:

* **Ingesta Visual:** Procesamiento de planos arquitectónicos para generar la lista de requerimientos (BOM) automáticamente.  
* **Cotización Autónoma B2B:** Despliegue de agentes mediante WhatsApp que negocian y scrapean precios de proveedores locales en tiempo real.  
* **Matriz Nacional de Precios:** Un motor de datos masivo que predice fluctuaciones de costos de materiales y logística (fletes) dependiendo de la zona geográfica.

## **3\. Scope del MVP (Fase 1 \- Alta Velocidad)**

Para evitar el *scope creep* y la latencia destructiva de los proveedores, el MVP divide la arquitectura en dos sistemas independientes y asíncronos.

### **3.1. Stack Tecnológico Consolidado**

| Componente | Tecnología / Herramienta | Función Principal   |
| :---- | :---- | :---- |
| Infraestructura | Antigravity | Levantamiento de entornos sin fricción. |
| Backend Core | FastAPI | Alta velocidad y baja latencia para la lógica dura. |
| Frontend | Vue.js | Dashboard de revisión humana (orquestado por Filis). |
| Base de Datos | PostgreSQL (Neon) | Almacenamiento de la matriz relacional de precios unitarios. |
| Workers / Asincronía | Celery \+ Redis | Ejecución de procesos en background sin bloquear la interfaz. |
| Motor IA | Hermes (MCP) | Match semántico y análisis de requerimientos. |
| Comunicaciones B2B | Evolution API (Baileys) | Conexión a WhatsApp para scrapeo de precios de proveedores. |

### **3.2. Brics Core (Motor de Presupuestación Inmediata)**

Este es el flujo determinista que usará el usuario final:

1. **Ingesta:** Recepción de la volumetría / catálogo de conceptos crudo.  
2. **Match Semántico (El Umbral del 95%):** Hermes cruza la lista de requerimientos contra los datos históricos en PostgreSQL.  
   * Si la confianza del match es **≥ 95%**, se asigna el precio automáticamente.  
   * Si la confianza es **\< 95%** (o el material es muy volátil/crítico), se bloquea la automatización y se empuja a la Matriz de Fricción.  
3. **Matriz de Fricción (Dashboard Vue.js):** Interfaz de alta velocidad donde el humano revisa únicamente las excepciones. Se ajustan precios atípicos y se aprueba.  
4. **Output Determinista:** Generación de un reporte PDF crudo y funcional que incluye:  
   * Presupuesto total desglosado.  
   * Reporte de labor manual pendiente (qué precios exactos faltan por confirmar en campo).

### **3.3. Brics Data Engine (Motor ETL y Asíncrono)**

El microservicio que alimenta la base de datos sin bloquear al usuario en su flujo de presupuestación:

1. **ETL Histórico (Paso Cero):** Estandarización manual y semi-automatizada de los 15 años de Excels/PDFs históricos de la constructora familiar para inyectarlos a Neon. Esta es la materia prima crítica del MVP.  
2. **Cotizador Asíncrono (Workers):** Tareas en background gestionadas por Celery que se conectan a Evolution API. Disparan solicitudes de precios a proveedores por WhatsApp, procesan las respuestas y actualizan pasivamente los promedios en PostgreSQL.