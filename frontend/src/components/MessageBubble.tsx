import { ChatMessage } from '../types';
import { User, Bot, Code } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import Plot from 'react-plotly.js';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 message-bubble ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center">
            <Bot className="w-5 h-5 text-primary-600" />
          </div>
        </div>
      )}
      
      <div className={`flex-1 max-w-3xl ${isUser ? 'flex justify-end' : ''}`}>
        <div
          className={`rounded-lg px-4 py-3 ${
            isUser
              ? 'bg-primary-600 text-white'
              : 'bg-white border border-gray-200 text-gray-900'
          }`}
        >
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
          
        {/* Generated Code - Direct View */}
        {message.generated_code && !isUser && (
          <div className="mt-3 bg-gray-900 rounded-lg overflow-hidden">
            <div className="px-3 py-2 text-xs font-medium text-gray-400 border-b border-gray-800 flex items-center gap-2">
              <Code className="w-4 h-4" />
              Generated Code
            </div>
            <pre className="p-3 text-xs overflow-x-auto text-gray-100">
              <code>{message.generated_code}</code>
            </pre>
          </div>
        )}
          
          {/* Chart */}
          {message.chart_data && !isUser && (
            <div className="mt-4 bg-white p-2 rounded-lg">
              <Plot
                data={message.chart_data.data.data}
                layout={{
                  ...message.chart_data.data.layout,
                  autosize: true,
                  height: 400,
                }}
                config={{ responsive: true }}
                className="w-full"
              />
            </div>
          )}
          
          {/* Execution Result */}
          {message.execution_result && !isUser && (
            <div className="mt-3 bg-gray-50 p-3 rounded-lg">
              <p className="text-xs font-medium text-gray-700 mb-2">Result:</p>
              <pre className="text-xs overflow-x-auto">
                {JSON.stringify(message.execution_result, null, 2)}
              </pre>
            </div>
          )}
          
          {message.timestamp && (
            <p className={`text-xs mt-2 ${isUser ? 'text-primary-100' : 'text-gray-500'}`}>
              {new Date(message.timestamp).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>
      
      {isUser && (
        <div className="flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
            <User className="w-5 h-5 text-gray-600" />
          </div>
        </div>
      )}
    </div>
  );
}
