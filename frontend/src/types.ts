export interface Product {
  id: number;
  sku: string;
  name: string;
  category: string;
  metal: string;
  purity: number;
  active: boolean;
}

export type RateUnit = "gram" | "tola" | "kilogram";

export interface MetalRate {
  id: number;
  metal: string;
  purity: number;
  rate_per_gram: number | string;
  unit: RateUnit;
  entered_rate: number | string;
  source_note?: string | null;
  verified_by?: string | null;
  verified_at?: string | null;
  active: boolean;
}

export interface InventoryRow {
  product_id: number;
  location: string;
  balance_grams: number | string;
}

export type TransactionKind =
  | "purchase"
  | "sale"
  | "sales_return"
  | "stock_adjustment"
  | "stock_transfer";

export interface Transaction {
  id: number;
  reference: string;
  kind: TransactionKind;
  status: "active" | "cancelled";
  product_id: number;
  party_id?: number | null;
  quantity_grams: number | string;
  rate_per_gram: number | string;
  charges: number | string;
  total_amount: number | string;
  amount_paid: number | string;
  party_name: string;
  location: string;
  destination?: string | null;
  created_by: string;
  cancelled_by?: string | null;
  cancel_reason?: string | null;
  created_at?: string | null;
  transaction_date?: string | null;
}

export interface Payment {
  id: number;
  transaction_id: number;
  amount: number | string;
  method: string;
  note: string;
  paid_at: string;
  recorded_by: string;
}

export interface Party {
  id: number;
  name: string;
  kind: "customer" | "supplier" | "both";
  phone: string;
  address: string;
  notes: string;
  active: boolean;
  created_at: string;
  receivable: number | string;
  payable: number | string;
  net: number | string;
}

export interface AuditEntry {
  id: number;
  username: string;
  action: string;
  entity_type: string;
  entity_id: string;
  detail: string;
  created_at: string;
}

export interface AppSettings {
  business_name: string;
  currency: string;
  default_location: string;
  allow_negative_stock: string;
}

export interface BackupInfo {
  filename: string;
  size_bytes: number;
  kind: "pgdump" | "json";
  encrypted: boolean;
  created_at: string;
}

export interface DashboardData {
  stock_grams: number | string;
  product_count: number;
  party_count: number;
  transaction_count: number;
  inventory_value: number | string;
  unvalued_products: {
    product_id: number;
    name: string;
    balance_grams: number | string;
  }[];
  purchases: {
    total_amount: number | string;
    amount_paid: number | string;
    remaining_amount: number | string;
  };
  sales: {
    total_amount: number | string;
    amount_paid: number | string;
    remaining_amount: number | string;
  };
  active_rates: {
    id: number;
    metal: string;
    purity: number | string;
    rate_per_gram: number | string;
    unit: RateUnit;
    entered_rate: number | string;
  }[];
  recent_transactions: {
    id: number;
    reference: string;
    kind: TransactionKind;
    product_id: number;
    party_name: string;
    quantity_grams: number | string;
    total_amount: number | string;
    amount_paid: number | string;
    transaction_date: string | null;
    created_at: string;
  }[];
}

export interface ReportSummary {
  purchase: {
    total_amount: number | string;
    amount_paid: number | string;
    remaining_amount: number | string;
  };
  sale: {
    total_amount: number | string;
    amount_paid: number | string;
    remaining_amount: number | string;
  };
  sales_returns: { count: number };
  stock_adjustments: { count: number };
}

export interface ProfitEstimate {
  sales_total: number | string;
  purchases_total: number | string;
  sales_returns_value: number | string;
  estimated_profit: number | string;
  is_estimate: boolean;
  note: string;
}

export interface OutstandingItem {
  transaction_id: number;
  reference: string;
  kind: "purchase" | "sale";
  party_name: string;
  created_at: string;
  total_amount: number | string;
  amount_paid: number | string;
  remaining_amount: number | string;
  location: string;
}

export interface CashflowRow {
  payment_id: number;
  reference: string;
  kind: string;
  party_name: string;
  amount: number | string;
  method: string;
  note: string;
  paid_at: string;
  direction: "received" | "paid";
}

export interface CashflowReport {
  money_received: number | string;
  money_paid: number | string;
  net_cashflow: number | string;
  payment_count: number;
  items: CashflowRow[];
}

export interface UserData {
  id: number;
  username: string;
  role: string;
  active: boolean;
  created_at: string;
}
