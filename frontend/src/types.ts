export interface Product {
  id: number;
  sku: string;
  name: string;
  category: string;
  metal: string;
  purity: number;
  active: boolean;
}

export interface MetalRate {
  id: number;
  metal: string;
  purity: number;
  rate_per_gram: number | string;
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

export interface Transaction {
  id: number;
  reference: string;
  kind: "purchase" | "sale";
  product_id: number;
  quantity_grams: number | string;
  rate_per_gram: number | string;
  charges: number | string;
  total_amount: number | string;
  amount_paid: number | string;
  party_name: string;
  location?: string;
  destination?: string | null;
  created_by?: string;
}
