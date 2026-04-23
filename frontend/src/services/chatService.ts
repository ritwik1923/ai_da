import api from './api';
import { UploadedFile, ChatRequest, ChatResponse, ConversationHistory, FilePreview, KPIResponse } from '../types';

type BackendColumn = string | { name?: string; dtype?: string };

function normalizeUploadedFile(file: any): UploadedFile {
  const rawColumns: BackendColumn[] = Array.isArray(file?.columns) ? file.columns : [];
  const columns = rawColumns
    .map((col) => {
      if (typeof col === 'string') return col;
      if (col && typeof col === 'object' && typeof col.name === 'string') return col.name;
      return '';
    })
    .filter((col): col is string => Boolean(col));

  return {
    ...file,
    columns,
  } as UploadedFile;
}

export const chatService = {
  // Send a message
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post('/api/chat/message', request);
    return response.data;
  },

  // Get conversation history
  getHistory: async (sessionId: string): Promise<ConversationHistory> => {
    const response = await api.get(`/api/chat/history/${sessionId}`);
    return response.data;
  },

  // Create new session
  createSession: async (): Promise<{ session_id: string }> => {
    const response = await api.post('/api/chat/new-session');
    return response.data;
  },

  // Delete session
  deleteSession: async (sessionId: string): Promise<void> => {
    await api.delete(`/api/chat/session/${sessionId}`);
  },
};

export const fileService = {
  // Upload file
  uploadFile: async (file: File): Promise<UploadedFile> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/files/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // Get all files
  getFiles: async (): Promise<UploadedFile[]> => {
    const response = await api.get('/api/files');
    return Array.isArray(response.data)
      ? response.data.map((file) => normalizeUploadedFile(file))
      : [];
  },

  // Get file details
  getFile: async (fileId: number): Promise<UploadedFile> => {
    const response = await api.get(`/api/files/${fileId}`);
    return normalizeUploadedFile(response.data);
  },

  // Delete file
  deleteFile: async (fileId: number): Promise<void> => {
    await api.delete(`/api/files/${fileId}`);
  },

  // Preview file data
  previewFile: async (fileId: number, limit: number = 10): Promise<FilePreview> => {
    const response = await api.get(`/api/files/${fileId}/preview?limit=${limit}`);
    return response.data;
  },

  // Get KPI summary for a file
  getFileKpis: async (fileId: number): Promise<KPIResponse> => {
    const response = await api.get(`/api/files/${fileId}/kpis`);
    return response.data;
  },
};
