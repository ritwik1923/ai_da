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
