// Cliente oficial de API REST para el Servicio de Inventario Industrial (FastAPI)
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PartAvailability {
  part_id: number;
  name?: string | null;
  sku?: string | null;
  on_hand: number;
  reserved: number;
  available: number;
  locations: {
    location_id: number;
    code?: string;
    on_hand: number;
    reserved: number;
    available: number;
  }[];
}

export interface LedgerEntry {
  movement_id: number | string;
  type: "receipt" | "issue" | "transfer_out" | "transfer_in" | "adjustment" | string;
  part_id: number;
  location_id: number;
  quantity: number;
  occurred_at: string;
  reference?: string | null;
  balance: number;
}

export interface LedgerResponse {
  part_id: number;
  entries: LedgerEntry[];
}

export interface MaterialLine {
  inspection_item_id: number;
  bom_line_id: number;
  part_id?: number | null;
  name: string;
  required?: number | null;
  reserved: number;
  issued: number;
  missing?: number | null;
}

export interface WorkOrderMaterialsResponse {
  work_order_id: number;
  code: string;
  lines: MaterialLine[];
}

export interface ShortageItem {
  work_order_id: number;
  work_order_code: string;
  part_id?: number | null;
  name: string;
  missing_quantity?: number | null;
  inspection_item_id: number;
  opened_at?: string | null;
}

export interface ReorderSuggestionItem {
  part_id: number;
  sku?: string | null;
  name: string;
  suggested_quantity: number;
  work_order_ids: number[];
}

export interface UnmatchedReceiptItem {
  id: number | string;
  purchase_line_id: number;
  part_number: string;
  description?: string;
  quantity: number;
  unit_price?: string | null;
  currency?: string | null;
  received_at: string;
  work_order_code?: string | null;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = `Error HTTP ${res.status}: ${res.statusText}`;
    try {
      const errJson = await res.json();
      if (errJson.detail) {
        errorMsg = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export const api = {
  // Verificación de conexión
  async checkHealth(): Promise<{ status: string; service: string }> {
    const res = await fetch(`${API_BASE_URL}/health`);
    return handleResponse(res);
  },

  // 1. Disponibilidad de pieza
  async getAvailability(partId: number): Promise<PartAvailability> {
    const res = await fetch(`${API_BASE_URL}/parts/${partId}/availability`);
    return handleResponse(res);
  },

  // 2. Kardex / Libro Mayor
  async getLedger(partId: number): Promise<LedgerResponse> {
    const res = await fetch(`${API_BASE_URL}/parts/${partId}/ledger`);
    return handleResponse(res);
  },

  // 3. Materiales de Orden de Trabajo
  async getMaterials(workOrderCode: string): Promise<WorkOrderMaterialsResponse> {
    const res = await fetch(`${API_BASE_URL}/work-orders/${encodeURIComponent(workOrderCode)}/materials`);
    return handleResponse(res);
  },

  // 4. Faltantes activos
  async getShortages(workOrderCode?: string): Promise<{ items: ShortageItem[] }> {
    const url = workOrderCode
      ? `${API_BASE_URL}/shortages?work_order_code=${encodeURIComponent(workOrderCode)}`
      : `${API_BASE_URL}/shortages`;
    const res = await fetch(url);
    return handleResponse(res);
  },

  // 5. Sugerencias de reorden
  async getReorderSuggestions(): Promise<{ items: ReorderSuggestionItem[] }> {
    const res = await fetch(`${API_BASE_URL}/purchasing/reorder-suggestions`);
    return handleResponse(res);
  },

  // 6. Recepciones no relacionadas
  async getUnmatchedReceipts(): Promise<{ items: UnmatchedReceiptItem[] }> {
    const res = await fetch(`${API_BASE_URL}/purchasing/unmatched-receipts`);
    return handleResponse(res);
  },

  // 7. Resolver recepción ambigua
  async resolveUnmatchedReceipt(id: number | string, partId: number, locationId?: number) {
    const res = await fetch(`${API_BASE_URL}/purchasing/unmatched-receipts/${id}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ part_id: partId, location_id: locationId }),
    });
    return handleResponse(res);
  },

  // 8. Salida de material
  async issueMaterial(data: {
    work_order_code: string;
    part_id: number;
    location_id: number;
    quantity: number;
    issued_by: string | number;
  }) {
    const res = await fetch(`${API_BASE_URL}/operations/issue`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  // 9. Transferencia entre estantes
  async transferMaterial(data: {
    part_id: number;
    from_location_id: number;
    to_location_id: number;
    quantity: number;
  }) {
    const res = await fetch(`${API_BASE_URL}/operations/transfer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  // 10. Conteo físico y ajuste
  async countAdjustment(data: {
    location_id: number;
    reason: string;
    lines: { part_id: number; counted_quantity: number }[];
  }) {
    const res = await fetch(`${API_BASE_URL}/operations/count`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return handleResponse(res);
  },
};
