import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Brain, Send, ArrowLeft, FileSpreadsheet, Code, Loader } from 'lucide-react';
import { chatService } from '../services/chatService';
import { ChatMessage, UploadedFile } from '../types';
import MessageBubble from '../components/MessageBubble';
import FileUpload from '../components/FileUpload';

export default function ChatPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState<string>('');
  const [fileId, setFileId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [fileInfo, setFileInfo] = useState<UploadedFile | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize session
  useEffect(() => {
    const initSession = async () => {
      const { session_id } = await chatService.createSession();
      setSessionId(session_id);
      
      // Get file ID from navigation state
      if (location.state?.fileId) {
        setFileId(location.state.fileId);
      }
    };
    initSession();
  }, [location.state]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || !sessionId) return;
    if (!fileId) {
      alert('Please upload a file first');
      return;
    }

    const userMessage: ChatMessage = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await chatService.sendMessage({
        session_id: sessionId,
        message: input,
        file_id: fileId,
      });

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: response.timestamp,
        generated_code: response.generated_code,
        chart_data: response.chart_data,
        execution_result: response.execution_result,
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUploaded = (file: UploadedFile) => {
    setFileId(file.id);
    setFileInfo(file);
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <Brain className="w-6 h-6 text-primary-600" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">AI Data Analyst</h1>
                {fileInfo && (
                  <p className="text-sm text-gray-600">
                    {fileInfo.original_filename} ({fileInfo.row_count} rows)
                  </p>
                )}
              </div>
            </div>
            {!fileId && (
              <div className="text-sm text-amber-600 font-medium">
                Please upload a file to start
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex-1 overflow-hidden flex">
        {/* Chat Area */}
        <div className="flex-1 flex flex-col">
          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-4xl mx-auto space-y-4">
              {messages.length === 0 && (
                <div className="text-center py-12">
                  <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-xl font-semibold text-gray-600 mb-2">
                    Ready to analyze your data
                  </h3>
                  <p className="text-gray-500">
                    Ask me anything about your uploaded data!
                  </p>
                </div>
              )}
              
              {messages.map((message, idx) => (
                <MessageBubble key={idx} message={message} />
              ))}
              
              {loading && (
                <div className="flex items-center gap-2 text-gray-500">
                  <Loader className="w-5 h-5 animate-spin" />
                  <span>Analyzing data...</span>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-200 bg-white px-4 py-4">
            <div className="max-w-4xl mx-auto">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask a question about your data..."
                  className="input-field"
                  disabled={!fileId || loading}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!input.trim() || !fileId || loading}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Example: "What are the top 5 products by sales?" or "Show me trends over time"
              </p>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-80 border-l border-gray-200 bg-white p-4 overflow-y-auto">
          <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5" />
            Data File
          </h3>
          
          {!fileId ? (
            <FileUpload onFileUploaded={handleFileUploaded} compact />
          ) : (
            fileInfo && (
              <div className="space-y-4">
                <div className="bg-primary-50 p-3 rounded-lg">
                  <p className="font-medium text-gray-900">{fileInfo.original_filename}</p>
                  <p className="text-sm text-gray-600 mt-1">
                    {fileInfo.row_count} rows × {fileInfo.columns.length} columns
                  </p>
                </div>
                
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Columns:</h4>
                  <div className="space-y-1">
                    {fileInfo.columns.map((col, idx) => (
                      <div key={idx} className="text-sm text-gray-600 bg-gray-50 px-2 py-1 rounded">
                        {col}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          )}

          <div className="mt-8">
            <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
              <Code className="w-5 h-5" />
              Example Queries
            </h3>
            <div className="space-y-2">
              {[
                "Show summary statistics",
                "Top 10 by revenue",
                "Find null values",
                "Show distribution",
                "Correlation analysis"
              ].map((query, idx) => (
                <button
                  key={idx}
                  onClick={() => setInput(query)}
                  className="w-full text-left text-sm text-gray-700 hover:bg-gray-100 px-3 py-2 rounded-lg transition-colors"
                  disabled={!fileId}
                >
                  {query}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
