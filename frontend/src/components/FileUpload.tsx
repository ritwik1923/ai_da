import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileSpreadsheet, Loader } from 'lucide-react';
import { useState } from 'react';
import { fileService } from '../services/chatService';
import { UploadedFile } from '../types';

interface FileUploadProps {
  onFileUploaded: (file: UploadedFile) => void;
  compact?: boolean;
}

export default function FileUpload({ onFileUploaded, compact = false }: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;

    const file = acceptedFiles[0];
    setUploading(true);
    setError(null);

    try {
      const uploadedFile = await fileService.uploadFile(file);
      onFileUploaded(uploadedFile);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to upload file');
    } finally {
      setUploading(false);
    }
  }, [onFileUploaded]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    maxFiles: 1,
    // Frontend limit: 1GB (backend will enforce actual production 100MB limit)
    // Development: No practical limit | Production: Backend enforces 100MB
    maxSize: 1024 * 1024 * 1024, // 1GB - effectively no limit for development
  });

  if (compact) {
    return (
      <div>
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors
            ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'}
            ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          <input {...getInputProps()} disabled={uploading} />
          {uploading ? (
            <Loader className="w-8 h-8 text-primary-500 mx-auto animate-spin" />
          ) : (
            <>
              <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-sm text-gray-600">Upload CSV/Excel</p>
            </>
          )}
        </div>
        {error && (
          <p className="text-sm text-red-600 mt-2">{error}</p>
        )}
      </div>
    );
  }

  return (
    <div className="card">
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'}
          ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input {...getInputProps()} disabled={uploading} />
        
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <Loader className="w-12 h-12 text-primary-500 animate-spin" />
            <p className="text-lg font-medium text-gray-700">Uploading...</p>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-center gap-3 mb-4">
              <Upload className="w-12 h-12 text-primary-500" />
              <FileSpreadsheet className="w-12 h-12 text-primary-400" />
            </div>
            
            {isDragActive ? (
              <p className="text-lg font-medium text-primary-600">Drop your file here...</p>
            ) : (
              <>
                <p className="text-lg font-medium text-gray-700 mb-2">
                  Drag & drop your data file here
                </p>
                <p className="text-gray-500 mb-4">or click to browse</p>
                <button className="btn-primary">
                  Select File
                </button>
              </>
            )}
            
            <p className="text-sm text-gray-500 mt-4">
              Supports CSV, XLS, XLSX (max 50MB)
            </p>
          </>
        )}
      </div>
      
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
}
