export type AssetClass = "equity" | "fx" | "commodity" | "bond";

export interface Instrument {
  symbol: string;
  name: string;
  assetClass: AssetClass;
  price: number;
  changePct: number;
  volume: number;
  currency: string;
}

export interface Kpi {
  id: string;
  label: string;
  value: number;
  format: "currency" | "number" | "percent";
  deltaPct: number;
}

export type ClientTier = "institutional" | "corporate" | "private";

export interface Client {
  id: string;
  name: string;
  tier: ClientTier;
  region: string;
  contact: string;
  email: string;
  aum: number;
  lastActivity: string;
  notes: string;
}

export type ReportStatus = "draft" | "published" | "failed" | "scheduled";

export interface Report {
  id: string;
  title: string;
  date: string;
  status: ReportStatus;
  author: string;
  pages: number;
}

export type Theme = "light" | "dark";

export interface Settings {
  theme: Theme;
  emailAlerts: boolean;
  pushAlerts: boolean;
  weeklyDigest: boolean;
}

export type TradeSide = "buy" | "sell";

export type TradeStatus = "filled" | "partial" | "cancelled";

export interface Trade {
  id: string;
  symbol: string;
  assetClass: AssetClass;
  side: TradeSide;
  quantity: number;
  filledQuantity: number;
  price: number;
  currency: string;
  executedAt: string;
  clientId: string;
  trader: string;
  venue: string;
  status: TradeStatus;
  fees: number;
}

export interface TradeFilters {
  side: TradeSide | "all";
  assetClass: AssetClass | "all";
  from: string;
  to: string;
  symbol: string;
}

export interface Holding {
  id: string;
  symbol: string;
  quantity: number;
  avgCost: number;
  openedAt: string;
  book: string;
}

export interface Position extends Holding {
  name: string;
  assetClass: AssetClass;
  currency: string;
  price: number;
  changePct: number;
  marketValueUsd: number;
  costBasisUsd: number;
  unrealizedPnlUsd: number;
  unrealizedPnlPct: number;
  dayChangeUsd: number;
  weight: number;
}

export interface AllocationSlice {
  assetClass: AssetClass;
  valueUsd: number;
  weight: number;
}

export interface PortfolioTotals {
  marketValueUsd: number;
  costBasisUsd: number;
  unrealizedPnlUsd: number;
  unrealizedPnlPct: number;
  dayChangeUsd: number;
  positions: number;
}

export type FxRates = Record<string, number>;

export interface PricePoint {
  date: string;
  close: number;
}

export interface InstrumentStats {
  symbol: string;
  exchange: string;
  sector: string;
  marketCap: number | null;
  peRatio: number | null;
  dividendYield: number | null;
  open: number;
  dayHigh: number;
  dayLow: number;
  prevClose: number;
  rangeHigh: number;
  rangeLow: number;
  avgVolume: number;
}

export type NotificationKind = "trade" | "report" | "client" | "system";

export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  createdAt: string;
  read: boolean;
  link?: string;
}

export interface ClientNote {
  id: string;
  text: string;
  author: string;
  createdAt: string;
}

export type SortDirection = "asc" | "desc";

export interface SortState {
  key: string;
  direction: SortDirection;
}
