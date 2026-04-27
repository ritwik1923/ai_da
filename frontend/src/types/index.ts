export interface UploadedFile {
  id: number;
  filename: string;
  original_filename: string;
  file_size: number;
  row_count: number;
  columns: string[];
  upload_date: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
  generated_code?: string;
  execution_result?: any;
  chart_data?: any;
}

export interface ChatRequest {
  session_id: string;
  message: string;
  file_id?: number;
}

export interface ChatResponse {
  session_id: string;
  response: string;
  generated_code?: string;
  execution_result?: any;
  chart_data?: any;
  timestamp: string;
}

export interface ConversationHistory {
  session_id: string;
  messages: ChatMessage[];
  file_info?: UploadedFile;
}

export interface FilePreview {
  columns: string[];
  data: any[];
  total_rows: number;
}

export interface KPIStat {
  label: string;
  value: string;
}

export interface KPIChart {
  title: string;
  data: any;
}

export interface DataQualityInsight {
  metric: string;
  status: 'good' | 'warning' | 'critical';
  description: string;
}

export interface AnalysisInsight {
  title: string;
  description: string;
  key_findings?: string[];
  recommendations?: string[];
}

export interface VisualRecommendation {
  title: string;
  description: string;
  suggested_query: string;
  generated_code?: string;
  chart_data?: any;
}

export interface KPIResponse {
  file_id: number;
  summary: {
    rows: number;
    columns: number;
    numeric_columns: number;
    categorical_columns: number;
    missing_values: number;
    missing_percent: number;
  };
  metrics: KPIStat[];
  charts: KPIChart[];
  top_categories?: Array<{ column: string; value: string; count: number }>;
  date_insights?: string[];
  // AI-powered analysis fields
  data_quality?: DataQualityInsight[];
  analysis_insights?: AnalysisInsight[];
  ai_summary?: string;
  key_metrics?: string[];
  visual_recommendations?: VisualRecommendation[];
}
