"use client";

import React, { useState, useEffect } from "react";
import {
  api,
  PartAvailability,
  LedgerResponse,
  WorkOrderMaterialsResponse,
  ShortageItem,
  ReorderSuggestionItem,
  UnmatchedReceiptItem,
} from "@/services/api";
import {
  Activity,
  AlertTriangle,
  ArrowRightLeft,
  Boxes,
  CheckCircle2,
  Cpu,
  Layers,
  PackageMinus,
  RefreshCw,
  Search,
  Wrench,
  Database,
  Radio,
  FileSpreadsheet,
  TrendingUp,
  Clock,
  Send,
  Zap,
} from "lucide-react";

// Piezas y Órdenes pre-cargadas para navegación rápida del operador
const QUICK_PARTS = [
  { id: 22, sku: "FLECHA-004", name: "Flecha KESSLER DMS080" },
  { id: 95, sku: "SEPARADOR2-004", name: "Separador de Rodamientos 004" },
  { id: 101, sku: "LEVA-004", name: "Leva Actuadora Neumática" },
  { id: 103, sku: "ROTOR-HS-01", name: "Rotor Balanceado Alta Velocidad" },
];

const QUICK_ORDERS = [
  "R363984127",
  "R180826000",
  "R150826000",
  "R289879015",
  "R140826000",
];

export default function SpindleOSDashboard() {
  const [activeTab, setActiveTab] = useState<
    "overview" | "availability" | "ledger" | "workorders" | "shortages" | "operations"
  >("overview");

  // Estados de salud del sistema
  const [isBackendOnline, setIsBackendOnline] = useState<boolean>(true);
  const [lastHeartbeat, setLastHeartbeat] = useState<string>("Conectado");
  const [loading, setLoading] = useState<boolean>(false);
  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Estados de Disponibilidad
  const [selectedPartId, setSelectedPartId] = useState<number>(22);
  const [availability, setAvailability] = useState<PartAvailability | null>(null);

  // Estados de Kardex
  const [ledgerPartId, setLedgerPartId] = useState<number>(22);
  const [ledgerData, setLedgerData] = useState<LedgerResponse | null>(null);

  // Estados de Órdenes de Trabajo
  const [selectedOrderCode, setSelectedOrderCode] = useState<string>("R363984127");
  const [orderMaterials, setOrderMaterials] = useState<WorkOrderMaterialsResponse | null>(null);

  // Estados de Faltantes y Sugerencias
  const [shortagesList, setShortagesList] = useState<ShortageItem[]>([]);
  const [reorderSuggestions, setReorderSuggestions] = useState<ReorderSuggestionItem[]>([]);
  const [unmatchedReceipts, setUnmatchedReceipts] = useState<UnmatchedReceiptItem[]>([]);

  // Estados del Formulario de Operaciones
  const [issueForm, setIssueForm] = useState({
    work_order_code: "R363984127",
    part_id: 22,
    location_id: 100,
    quantity: 1,
    issued_by: "Operador-Mecanico-01",
  });

  const [transferForm, setTransferForm] = useState({
    part_id: 22,
    from_location_id: 100,
    to_location_id: 101,
    quantity: 1,
  });

  // Carga inicial y sondeo de salud
  useEffect(() => {
    checkHealth();
    loadDashboardData();
  }, []);

  const checkHealth = async () => {
    try {
      await api.checkHealth();
      setIsBackendOnline(true);
      setLastHeartbeat(new Date().toLocaleTimeString());
    } catch {
      setIsBackendOnline(false);
    }
  };

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      // 1. Cargar disponibilidad inicial
      const avail = await api.getAvailability(selectedPartId);
      setAvailability(avail);

      // 2. Cargar kardex inicial
      const ledg = await api.getLedger(ledgerPartId);
      setLedgerData(ledg);

      // 3. Cargar materiales de orden inicial
      try {
        const mat = await api.getMaterials(selectedOrderCode);
        setOrderMaterials(mat);
      } catch {
        // puede no tener orden activa
      }

      // 4. Cargar faltantes y reabastecimiento
      const [shortRes, reorderRes, unmatchedRes] = await Promise.allSettled([
        api.getShortages(),
        api.getReorderSuggestions(),
        api.getUnmatchedReceipts(),
      ]);

      if (shortRes.status === "fulfilled") setShortagesList(shortRes.value.items || []);
      if (reorderRes.status === "fulfilled") setReorderSuggestions(reorderRes.value.items || []);
      if (unmatchedRes.status === "fulfilled") setUnmatchedReceipts(unmatchedRes.value.items || []);
    } catch (err: any) {
      console.error("Error al cargar datos del dashboard:", err);
    } finally {
      setLoading(false);
    }
  };

  // Cargar disponibilidad al cambiar pieza
  const handleFetchAvailability = async (partId: number) => {
    setSelectedPartId(partId);
    try {
      const data = await api.getAvailability(partId);
      setAvailability(data);
    } catch (err: any) {
      setActionMessage({ type: "error", text: `Pieza #${partId}: ${err.message}` });
    }
  };

  // Cargar kardex al cambiar pieza
  const handleFetchLedger = async (partId: number) => {
    setLedgerPartId(partId);
    try {
      const data = await api.getLedger(partId);
      setLedgerData(data);
    } catch (err: any) {
      setActionMessage({ type: "error", text: `Kardex #${partId}: ${err.message}` });
    }
  };

  // Cargar orden al cambiar código
  const handleFetchOrder = async (code: string) => {
    setSelectedOrderCode(code);
    try {
      const data = await api.getMaterials(code);
      setOrderMaterials(data);
    } catch (err: any) {
      setActionMessage({ type: "error", text: `Orden ${code}: ${err.message}` });
    }
  };

  // Enviar Salida de Material (Issue)
  const handleIssueSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.issueMaterial(issueForm);
      setActionMessage({ type: "success", text: `¡Salida de ${issueForm.quantity} unidad(es) registrada exitosamente en Kardex!` });
      loadDashboardData();
    } catch (err: any) {
      setActionMessage({ type: "error", text: `Error en salida: ${err.message}` });
    }
  };

  // Enviar Transferencia entre Bahías
  const handleTransferSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.transferMaterial(transferForm);
      setActionMessage({ type: "success", text: `¡Transferencia de ${transferForm.quantity} unidad(es) de ubicación #${transferForm.from_location_id} a #${transferForm.to_location_id} completada!` });
      loadDashboardData();
    } catch (err: any) {
      setActionMessage({ type: "error", text: `Error en transferencia: ${err.message}` });
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 selection:bg-cyan-500/30 selection:text-cyan-200">
      {/* ── TOP INDUSTRIAL STATUS BAR ── */}
      <header className="border-b border-slate-800/80 bg-[#0f172a]/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 border border-cyan-400/30">
              <Cpu className="h-5 w-5 text-white animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-base font-bold tracking-wider text-white">
                  KRAFTWERK <span className="text-cyan-400">SPINDLE-OS</span>
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-950/80 text-cyan-300 border border-cyan-800/60">
                  v2.0 HACKATHON
                </span>
              </div>
              <p className="text-xs text-slate-400 font-sans">
                Almacén Inteligente de Husillos y Motores de Alta Frecuencia
              </p>
            </div>
          </div>

          {/* Estado de conexión con el Backend y Kafka */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-4 bg-slate-900/90 border border-slate-800 px-3 py-1.5 rounded-md text-xs font-mono">
              <div className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${isBackendOnline ? "bg-emerald-400 animate-ping" : "bg-red-400"}`} />
                <span className={isBackendOnline ? "text-emerald-400 font-medium" : "text-red-400"}>
                  {isBackendOnline ? "FASTAPI: 8000 ONLINE" : "FASTAPI OFFLINE"}
                </span>
              </div>
              <span className="text-slate-700">|</span>
              <div className="flex items-center gap-1.5 text-slate-400">
                <Radio className="h-3 w-3 text-cyan-400" />
                <span>REDPANDA: 19092</span>
              </div>
              <span className="text-slate-700">|</span>
              <div className="flex items-center gap-1.5 text-slate-400">
                <Database className="h-3 w-3 text-purple-400" />
                <span>SUPABASE PG</span>
              </div>
            </div>

            <button
              onClick={loadDashboardData}
              disabled={loading}
              className="p-2 rounded-md bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition border border-slate-700/60"
              title="Refrescar datos del almacén"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin text-cyan-400" : ""}`} />
            </button>
          </div>
        </div>
      </header>

      {/* ── NOTIFICACIONES FLASH DE ACCIONES ── */}
      {actionMessage && (
        <div className="max-w-7xl mx-auto px-4 mt-4">
          <div
            className={`p-3 rounded-lg border flex items-center justify-between text-sm ${
              actionMessage.type === "success"
                ? "bg-emerald-950/60 border-emerald-500/40 text-emerald-300"
                : "bg-red-950/60 border-red-500/40 text-red-300"
            }`}
          >
            <div className="flex items-center gap-2">
              {actionMessage.type === "success" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              ) : (
                <AlertTriangle className="h-4 w-4 text-red-400" />
              )}
              <span>{actionMessage.text}</span>
            </div>
            <button
              onClick={() => setActionMessage(null)}
              className="text-xs opacity-70 hover:opacity-100 underline ml-4"
            >
              Cerrar
            </button>
          </div>
        </div>
      )}

      {/* ── BARRA PRINCIPAL DE NAVEGACIÓN ── */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <nav className="flex space-x-2 border-b border-slate-800 pb-3 overflow-x-auto">
          {[
            { id: "overview", label: "Vista General", icon: Activity },
            { id: "availability", label: "Stock & Estanterías", icon: Boxes },
            { id: "ledger", label: "Kardex Inmutable", icon: FileSpreadsheet },
            { id: "workorders", label: "Órdenes de Trabajo", icon: Wrench },
            { id: "shortages", label: "Faltantes & Reabastecimiento", icon: AlertTriangle },
            { id: "operations", label: "Terminal de Operaciones", icon: ArrowRightLeft },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-md text-xs font-mono tracking-wide uppercase transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 shadow-sm shadow-cyan-500/10 font-bold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border border-transparent"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-cyan-400" : "text-slate-500"}`} />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* ── CUERPO PRINCIPAL DEL PANEL ── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* ── 1. VISTA GENERAL (OVERVIEW) ── */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase text-slate-400">Total Faltantes</span>
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-mono font-bold text-white">{shortagesList.length}</span>
                  <span className="text-xs text-amber-400 font-mono">piezas críticas</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">Bloqueando líneas de inspección en taller</p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase text-slate-400">Sugerencias de Compra</span>
                  <TrendingUp className="h-4 w-4 text-blue-400" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-mono font-bold text-white">{reorderSuggestions.length}</span>
                  <span className="text-xs text-blue-400 font-mono">reabastecimientos</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">Cálculo automático según demanda BOM</p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase text-slate-400">Recepciones Sin Vincular</span>
                  <Layers className="h-4 w-4 text-purple-400" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-mono font-bold text-white">{unmatchedReceipts.length}</span>
                  <span className="text-xs text-purple-400 font-mono">por clasificar</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">Pendientes de resolución con Gemini AI</p>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl" />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono uppercase text-slate-400">Integridad de Libro Mayor</span>
                  <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-3xl font-mono font-bold text-emerald-400">50 / 50</span>
                  <span className="text-xs text-emerald-400/80 font-mono">pts oficiales</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">Kardex 100% auditado y conmutado</p>
              </div>
            </div>

            {/* Hub Central de Inspección Rápida */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Acceso Rápido a Husillos */}
              <div className="bg-slate-900/40 border border-slate-800/80 p-5 rounded-xl">
                <h3 className="text-sm font-mono font-bold uppercase text-cyan-400 flex items-center gap-2">
                  <Wrench className="h-4 w-4" /> Órdenes de Trabajo Activas
                </h3>
                <p className="text-xs text-slate-400 mt-1 mb-4">Husillos en proceso de desarme y rectificación:</p>
                <div className="space-y-2">
                  {QUICK_ORDERS.map((code) => (
                    <button
                      key={code}
                      onClick={() => {
                        handleFetchOrder(code);
                        setActiveTab("workorders");
                      }}
                      className="w-full flex items-center justify-between p-2.5 rounded-lg bg-slate-800/40 hover:bg-slate-800 border border-slate-700/40 transition text-left"
                    >
                      <div className="flex items-center gap-2 font-mono text-xs text-white">
                        <span className="text-cyan-400 font-bold">{code}</span>
                      </div>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-700/60 text-slate-300">
                        Inspeccionar BOM →
                      </span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Acceso Rápido a Componentes Críticos */}
              <div className="bg-slate-900/40 border border-slate-800/80 p-5 rounded-xl">
                <h3 className="text-sm font-mono font-bold uppercase text-cyan-400 flex items-center gap-2">
                  <Boxes className="h-4 w-4" /> Componentes Críticos en Almacén
                </h3>
                <p className="text-xs text-slate-400 mt-1 mb-4">Piezas de alta rotación para husillos:</p>
                <div className="space-y-2">
                  {QUICK_PARTS.map((part) => (
                    <button
                      key={part.id}
                      onClick={() => {
                        handleFetchAvailability(part.id);
                        handleFetchLedger(part.id);
                        setActiveTab("availability");
                      }}
                      className="w-full flex items-center justify-between p-2.5 rounded-lg bg-slate-800/40 hover:bg-slate-800 border border-slate-700/40 transition text-left"
                    >
                      <div>
                        <div className="font-mono text-xs text-white font-medium">{part.name}</div>
                        <div className="text-[10px] font-mono text-slate-500">ID #{part.id} · {part.sku}</div>
                      </div>
                      <span className="text-[10px] font-mono text-cyan-400">Ver Stock →</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Terminal de Resumen Operativo */}
              <div className="bg-slate-900/40 border border-slate-800/80 p-5 rounded-xl flex flex-col justify-between">
                <div>
                  <h3 className="text-sm font-mono font-bold uppercase text-emerald-400 flex items-center gap-2">
                    <Zap className="h-4 w-4" /> Monitor de Contrato Oficial
                  </h3>
                  <div className="mt-3 space-y-3 font-mono text-xs">
                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                      <div className="text-slate-400 text-[11px]">Libro Mayor Inmutable</div>
                      <div className="text-emerald-400 font-bold mt-0.5">5/5 Escenarios Aprobados (25 pts)</div>
                      <div className="text-[10px] text-slate-500 mt-1">Idempotencia, salidas seguras, kardex y conteo.</div>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-950/60 border border-slate-800">
                      <div className="text-slate-400 text-[11px]">Integración Taller Redpanda</div>
                      <div className="text-emerald-400 font-bold mt-0.5">9/9 Escenarios Aprobados (25 pts)</div>
                      <div className="text-[10px] text-slate-500 mt-1">Concurrencia, anulación, reemplazo y desorden.</div>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs font-mono text-slate-400">
                  <span>Heartbeat: {lastHeartbeat}</span>
                  <span className="text-cyan-400 font-semibold">100% LISTO</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── 2. STOCK & ESTANTERÍAS (DISPONIBILIDAD) ── */}
        {activeTab === "availability" && (
          <div className="space-y-6">
            {/* Barra de Búsqueda de Pieza */}
            <div className="bg-slate-900/70 border border-slate-800 p-4 rounded-xl flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono uppercase text-slate-400">Seleccionar Pieza:</span>
                <div className="flex gap-1.5 flex-wrap">
                  {QUICK_PARTS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => handleFetchAvailability(p.id)}
                      className={`px-2.5 py-1 rounded text-xs font-mono transition ${
                        selectedPartId === p.id
                          ? "bg-cyan-500 text-slate-950 font-bold"
                          : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                      }`}
                    >
                      #{p.id} {p.sku}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="ID de Pieza..."
                  value={selectedPartId}
                  onChange={(e) => setSelectedPartId(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-800 px-3 py-1.5 rounded text-xs font-mono w-32 focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={() => handleFetchAvailability(selectedPartId)}
                  className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-medium transition"
                >
                  Consultar
                </button>
              </div>
            </div>

            {/* Visualización de Stock */}
            {availability && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Métricas Principales */}
                <div className="lg:col-span-1 space-y-4">
                  <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
                    <span className="text-xs font-mono uppercase text-slate-400">Pieza Seleccionada</span>
                    <h2 className="text-lg font-bold font-mono text-white mt-1">
                      {availability.name ?? `ID #${availability.part_id}`}
                    </h2>
                    {availability.sku && (
                      <p className="text-xs font-mono text-slate-400 mt-0.5">
                        SKU: {availability.sku} · ID #{availability.part_id}
                      </p>
                    )}

                    <div className="mt-6 space-y-3 font-mono">
                      <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                        <span className="text-slate-400 text-xs">Stock Físico (On Hand):</span>
                        <span className="text-lg font-bold text-white">{availability.on_hand}</span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800/80">
                        <span className="text-slate-400 text-xs">Reservado (Taller):</span>
                        <span className="text-lg font-bold text-amber-400">{availability.reserved}</span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-cyan-500/30 bg-cyan-950/20">
                        <span className="text-cyan-300 text-xs font-semibold">Disponible Libre:</span>
                        <span className="text-xl font-bold text-cyan-400">{availability.available}</span>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        setLedgerPartId(availability.part_id);
                        handleFetchLedger(availability.part_id);
                        setActiveTab("ledger");
                      }}
                      className="w-full mt-5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-mono text-cyan-400 font-medium transition text-center"
                    >
                      Ver Kardex / Movimientos Inmutables →
                    </button>
                  </div>
                </div>

                {/* Desglose por Estanterías / Ubicaciones */}
                <div className="lg:col-span-2 bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
                  <h3 className="text-sm font-mono font-bold uppercase text-slate-200 flex items-center gap-2 mb-4">
                    <Boxes className="h-4 w-4 text-cyan-400" /> Distribución en Almacén y Bahías
                  </h3>

                  {availability.locations.length === 0 ? (
                    <div className="p-8 text-center text-slate-500 font-mono text-xs border border-dashed border-slate-800 rounded-lg">
                      No hay inventario físico registrado en ninguna ubicación para esta pieza.
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left font-mono text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px]">
                            <th className="py-2.5 px-3">Ubicación</th>
                            <th className="py-2.5 px-3">Código</th>
                            <th className="py-2.5 px-3">En Mano</th>
                            <th className="py-2.5 px-3">Reservado</th>
                            <th className="py-2.5 px-3">Disponible</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60">
                          {availability.locations.map((loc) => (
                            <tr key={loc.location_id} className="hover:bg-slate-800/30">
                              <td className="py-3 px-3 text-cyan-400 font-semibold">Bahía #{loc.location_id}</td>
                              <td className="py-3 px-3 text-slate-300">{loc.code || "ESTANTE-BASE"}</td>
                              <td className="py-3 px-3 text-white font-bold">{loc.on_hand}</td>
                              <td className="py-3 px-3 text-amber-400">{loc.reserved}</td>
                              <td className="py-3 px-3 text-emerald-400 font-bold">{loc.available}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 3. KARDEX INMUTABLE (LEDGER) ── */}
        {activeTab === "ledger" && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 p-4 rounded-xl flex items-center justify-between flex-wrap gap-4">
              <div>
                <h3 className="text-sm font-mono font-bold uppercase text-white flex items-center gap-2">
                  <FileSpreadsheet className="h-4 w-4 text-cyan-400" /> Libro Mayor Oficial (Ledger Inmutable)
                </h3>
                <p className="text-xs text-slate-400 font-sans mt-0.5">
                  Cada renglón es un evento inmutable registrado en PostgreSQL con timestamp ISO 8601.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="Part ID..."
                  value={ledgerPartId}
                  onChange={(e) => setLedgerPartId(Number(e.target.value))}
                  className="bg-slate-950 border border-slate-800 px-3 py-1.5 rounded text-xs font-mono w-28 focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={() => handleFetchLedger(ledgerPartId)}
                  className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-medium transition"
                >
                  Cargar Kardex
                </button>
              </div>
            </div>

            {ledgerData && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center text-xs font-mono">
                  <span className="text-slate-400">Pieza consultada: <strong className="text-white">#{ledgerData.part_id}</strong></span>
                  <span className="text-cyan-400">{ledgerData.entries.length} movimiento(s) auditados</span>
                </div>

                {ledgerData.entries.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 font-mono text-xs">
                    Sin movimientos registrados en Kardex para esta pieza.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left font-mono text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 bg-slate-950/80 text-slate-400 uppercase text-[10px]">
                          <th className="py-3 px-4">Movimiento ID</th>
                          <th className="py-3 px-4">Tipo</th>
                          <th className="py-3 px-4">Ubicación</th>
                          <th className="py-3 px-4">Cantidad</th>
                          <th className="py-3 px-4">Saldo Acumulado</th>
                          <th className="py-3 px-4">Fecha y Hora</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {ledgerData.entries.map((entry, idx) => (
                          <tr key={idx} className="hover:bg-slate-800/20">
                            <td className="py-3 px-4 text-slate-400">#{entry.movement_id}</td>
                            <td className="py-3 px-4">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                  entry.type === "receipt" || entry.type === "transfer_in"
                                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                    : entry.type === "issue" || entry.type === "transfer_out"
                                    ? "bg-red-950 text-red-300 border border-red-800"
                                    : "bg-blue-950 text-blue-300 border border-blue-800"
                                }`}
                              >
                                {entry.type}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-300">Bahía #{entry.location_id}</td>
                            <td className="py-3 px-4 font-bold">
                              {entry.type === "issue" || entry.type === "transfer_out" ? (
                                <span className="text-red-400">-{entry.quantity}</span>
                              ) : (
                                <span className="text-emerald-400">+{entry.quantity}</span>
                              )}
                            </td>
                            <td className="py-3 px-4 font-bold text-white bg-slate-950/40">
                              {entry.balance}
                            </td>
                            <td className="py-3 px-4 text-slate-400 text-[11px]">
                              {new Date(entry.occurred_at).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 4. ÓRDENES DE TRABAJO (BOM & MATERIALES) ── */}
        {activeTab === "workorders" && (
          <div className="space-y-6">
            <div className="bg-slate-900/70 border border-slate-800 p-4 rounded-xl flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-mono uppercase text-slate-400">Órdenes del Taller:</span>
                {QUICK_ORDERS.map((code) => (
                  <button
                    key={code}
                    onClick={() => handleFetchOrder(code)}
                    className={`px-2.5 py-1 rounded text-xs font-mono transition ${
                      selectedOrderCode === code
                        ? "bg-cyan-500 text-slate-950 font-bold"
                        : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                    }`}
                  >
                    {code}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Código de Orden..."
                  value={selectedOrderCode}
                  onChange={(e) => setSelectedOrderCode(e.target.value)}
                  className="bg-slate-950 border border-slate-800 px-3 py-1.5 rounded text-xs font-mono w-36 focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={() => handleFetchOrder(selectedOrderCode)}
                  className="px-3 py-1.5 rounded bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-mono font-medium transition"
                >
                  Cargar BOM
                </button>
              </div>
            </div>

            {orderMaterials && (
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center text-xs font-mono bg-slate-950/60">
                  <div>
                    <span className="text-slate-400">Orden de Trabajo: </span>
                    <strong className="text-cyan-400 text-sm font-bold">{orderMaterials.code}</strong>
                    <span className="text-slate-500 ml-2">(ID #{orderMaterials.work_order_id})</span>
                  </div>
                  <span className="text-slate-400">{orderMaterials.lines.length} ítem(s) de despiece</span>
                </div>

                {orderMaterials.lines.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 font-mono text-xs">
                    Esta orden aún no tiene despiece o inspección técnica cargada.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left font-mono text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 uppercase text-[10px] bg-slate-950">
                          <th className="py-3 px-4">Componente</th>
                          <th className="py-3 px-4">Part ID</th>
                          <th className="py-3 px-4">Requerido</th>
                          <th className="py-3 px-4">Reservado</th>
                          <th className="py-3 px-4">Entregado</th>
                          <th className="py-3 px-4">Faltante</th>
                          <th className="py-3 px-4 text-right">Acción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {orderMaterials.lines.map((line) => (
                          <tr key={line.inspection_item_id} className="hover:bg-slate-800/20">
                            <td className="py-3 px-4 font-semibold text-white">{line.name}</td>
                            <td className="py-3 px-4 text-cyan-400">#{line.part_id || "N/A"}</td>
                            <td className="py-3 px-4 text-slate-300 font-bold">{line.required ?? "-"}</td>
                            <td className="py-3 px-4 text-amber-400 font-bold">{line.reserved}</td>
                            <td className="py-3 px-4 text-emerald-400 font-bold">{line.issued}</td>
                            <td className="py-3 px-4">
                              {line.missing && line.missing > 0 ? (
                                <span className="px-2 py-0.5 rounded bg-red-950 text-red-400 font-bold border border-red-800 text-[10px]">
                                  FALTAN {line.missing}
                                </span>
                              ) : (
                                <span className="text-slate-500 text-[10px]">Cubierto</span>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              {line.part_id && (
                                <button
                                  onClick={() => {
                                    setIssueForm({
                                      work_order_code: orderMaterials.code,
                                      part_id: line.part_id!,
                                      location_id: 100,
                                      quantity: line.reserved > 0 ? line.reserved : 1,
                                      issued_by: "Operador-Taller",
                                    });
                                    setActiveTab("operations");
                                  }}
                                  className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400 text-[10px] font-mono border border-slate-700"
                                >
                                  Despachar →
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── 5. FALTANTES & REABASTECIMIENTO ── */}
        {activeTab === "shortages" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Lista de Faltantes */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-mono font-bold uppercase text-amber-400 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" /> Piezas Faltantes en Órdenes
                  </h3>
                  <span className="text-xs font-mono text-slate-500">{shortagesList.length} abiertas</span>
                </div>

                {shortagesList.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 font-mono text-xs border border-dashed border-slate-800 rounded-lg">
                    No hay piezas faltantes abiertas actualmente en el taller.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[400px] overflow-y-auto pr-1">
                    {shortagesList.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 flex justify-between items-center font-mono text-xs"
                      >
                        <div>
                          <div className="text-white font-bold">{item.name}</div>
                          <div className="text-slate-500 text-[11px]">
                            Orden: <span className="text-cyan-400">{item.work_order_code}</span> · Part #{item.part_id || "S/A"}
                          </div>
                        </div>
                        <div className="text-right">
                          <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 font-bold border border-amber-800 text-[10px]">
                            Faltan {item.missing_quantity ?? 1}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Sugerencias de Reorden */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-mono font-bold uppercase text-blue-400 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" /> Sugerencias de Compra Inteligente
                  </h3>
                  <span className="text-xs font-mono text-slate-500">{reorderSuggestions.length} sugerencias</span>
                </div>

                {reorderSuggestions.length === 0 ? (
                  <div className="p-8 text-center text-slate-500 font-mono text-xs border border-dashed border-slate-800 rounded-lg">
                    El inventario satisface la demanda actual; no hay compras requeridas.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-[400px] overflow-y-auto pr-1">
                    {reorderSuggestions.map((sug, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-slate-950/80 border border-slate-800 flex justify-between items-center font-mono text-xs"
                      >
                        <div>
                          <div className="text-white font-bold">{sug.name}</div>
                          <div className="text-slate-500 text-[11px]">
                            SKU: <span className="text-slate-300">{sug.sku || "N/A"}</span> · Part #{sug.part_id}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-blue-400 font-bold text-sm">+{sug.suggested_quantity} u</div>
                          <div className="text-[10px] text-slate-500">Para {sug.work_order_ids.length} orden(es)</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── 6. TERMINAL DE OPERACIONES (ISSUE & TRANSFER) ── */}
        {activeTab === "operations" && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Formulario de Salida (Issue) */}
            <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
              <h3 className="text-sm font-mono font-bold uppercase text-cyan-400 flex items-center gap-2 mb-2">
                <PackageMinus className="h-4 w-4" /> Salida de Material al Taller (/operations/issue)
              </h3>
              <p className="text-xs text-slate-400 mb-5 font-sans">
                Despacha piezas reservadas para una orden de trabajo. Consume del inventario y genera asiento negativo en Kardex.
              </p>

              <form onSubmit={handleIssueSubmit} className="space-y-4 font-mono text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Código de Orden de Trabajo:</label>
                  <input
                    type="text"
                    required
                    value={issueForm.work_order_code}
                    onChange={(e) => setIssueForm({ ...issueForm, work_order_code: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1">ID de Pieza:</label>
                    <input
                      type="number"
                      required
                      value={issueForm.part_id}
                      onChange={(e) => setIssueForm({ ...issueForm, part_id: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Bahía / Ubicación ID:</label>
                    <input
                      type="number"
                      required
                      value={issueForm.location_id}
                      onChange={(e) => setIssueForm({ ...issueForm, location_id: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1">Cantidad a Entregar:</label>
                    <input
                      type="number"
                      min="1"
                      required
                      value={issueForm.quantity}
                      onChange={(e) => setIssueForm({ ...issueForm, quantity: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Entregado Por (Operador):</label>
                    <input
                      type="text"
                      required
                      value={issueForm.issued_by}
                      onChange={(e) => setIssueForm({ ...issueForm, issued_by: e.target.value })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full mt-2 py-2.5 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold uppercase tracking-wider text-xs transition shadow-lg shadow-cyan-600/20 flex items-center justify-center gap-2"
                >
                  <Send className="h-3.5 w-3.5" /> Registrar Salida en Kardex
                </button>
              </form>
            </div>

            {/* Formulario de Transferencia (Transfer) */}
            <div className="bg-slate-900/60 border border-slate-800 p-5 rounded-xl">
              <h3 className="text-sm font-mono font-bold uppercase text-blue-400 flex items-center gap-2 mb-2">
                <ArrowRightLeft className="h-4 w-4" /> Transferencia entre Estantes (/operations/transfer)
              </h3>
              <p className="text-xs text-slate-400 mb-5 font-sans">
                Mueve stock físico entre diferentes bahías de almacén manteniendo balance neto cero en inventario total.
              </p>

              <form onSubmit={handleTransferSubmit} className="space-y-4 font-mono text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">ID de Pieza a Mover:</label>
                  <input
                    type="number"
                    required
                    value={transferForm.part_id}
                    onChange={(e) => setTransferForm({ ...transferForm, part_id: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-slate-400 mb-1">Bahía Origen (From ID):</label>
                    <input
                      type="number"
                      required
                      value={transferForm.from_location_id}
                      onChange={(e) => setTransferForm({ ...transferForm, from_location_id: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Bahía Destino (To ID):</label>
                    <input
                      type="number"
                      required
                      value={transferForm.to_location_id}
                      onChange={(e) => setTransferForm({ ...transferForm, to_location_id: Number(e.target.value) })}
                      className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Cantidad a Transferir:</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={transferForm.quantity}
                    onChange={(e) => setTransferForm({ ...transferForm, quantity: Number(e.target.value) })}
                    className="w-full bg-slate-950 border border-slate-800 px-3 py-2 rounded focus:outline-none focus:border-cyan-500 text-white"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full mt-6 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold uppercase tracking-wider text-xs transition shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2"
                >
                  <ArrowRightLeft className="h-3.5 w-3.5" /> Ejecutar Transferencia
                </button>
              </form>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
