import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileSpreadsheet, Brain, Sparkles } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { UploadedFile } from '../types';

export default function HomePage() {
  const navigate = useNavigate();
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);

  const handleFileUploaded = (file: UploadedFile) => {
    setUploadedFile(file);
    // Navigate to chat with file ID
    setTimeout(() => {
      navigate('/chat', { state: { fileId: file.id } });
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center gap-3">
            <Brain className="w-8 h-8 text-primary-600" />
            <h1 className="text-2xl font-bold text-gray-900">AI Data Analyst Agent</h1>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Sparkles className="w-12 h-12 text-primary-500" />
          </div>
          <h2 className="text-4xl font-bold text-gray-900 mb-4">
            Analyze Your Data with AI
          </h2>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Upload your CSV or Excel file and ask questions in plain English. 
            Our AI agent will generate insights, charts, and answers automatically.
          </p>
        </div>

        {/* Features */}
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          <div className="card text-center">
            <Upload className="w-12 h-12 text-primary-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Upload Data</h3>
            <p className="text-gray-600">
              Support for CSV and Excel files up to 10MB
            </p>
          </div>
          <div className="card text-center">
            <Brain className="w-12 h-12 text-primary-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Ask Questions</h3>
            <p className="text-gray-600">
              Natural language queries powered by GPT-4
            </p>
          </div>
          <div className="card text-center">
            <FileSpreadsheet className="w-12 h-12 text-primary-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Get Insights</h3>
            <p className="text-gray-600">
              AI-generated analysis with charts and code
            </p>
          </div>
        </div>

        {/* File Upload */}
        <div className="max-w-2xl mx-auto">
          <FileUpload onFileUploaded={handleFileUploaded} />
          
          {uploadedFile && (
            <div className="mt-6 card bg-green-50 border border-green-200">
              <div className="flex items-center gap-3">
                <FileSpreadsheet className="w-6 h-6 text-green-600" />
                <div className="flex-1">
                  <h4 className="font-semibold text-green-900">
                    {uploadedFile.original_filename}
                  </h4>
                  <p className="text-sm text-green-700">
                    {uploadedFile.row_count} rows × {uploadedFile.columns.length} columns
                  </p>
                </div>
                <p className="text-sm text-green-600 font-medium">
                  Redirecting to chat...
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Example Queries */}
        <div className="mt-16 max-w-4xl mx-auto">
          <h3 className="text-2xl font-bold text-center mb-8">Example Questions You Can Ask</h3>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              "What are the top 5 products by revenue?",
              "Show me sales trends over the last 6 months",
              "Why did sales drop in July?",
              "Which region has the highest growth rate?",
              "Compare this quarter to last quarter",
              "What's the correlation between price and sales?"
            ].map((query, idx) => (
              <div key={idx} className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
                <p className="text-gray-700">"{query}"</p>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-600">
            Built with FastAPI, LangChain, React & GPT-4 • Portfolio Project for AI Engineering
          </p>
        </div>
      </footer>
    </div>
  );
}
