import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, FileSpreadsheet, Loader, X, Maximize2, Copy, Check } from 'lucide-react';
import Plot from 'react-plotly.js';
import { fileService } from '../services/chatService';
import { UploadedFile, KPIResponse } from '../types';
import FileUpload from '../components/FileUpload';
import {
  enhanceChartLayout,
  enhanceChartData,
  getProfessionalChartConfig,
} from '../utils/chartTheme';

interface VisualRecommendation {
  title: string;
  description: string;
  suggested_query: string;
  generated_code?: string;
  chart_data?: {
    data: {
      data: any[];
      layout: any;
    };
  };
}

export default function KPIPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [fileId, setFileId] = useState<number | null>(null);
  const [fileInfo, setFileInfo] = useState<UploadedFile | null>(null);
  const [kpiData, setKpiData] = useState<KPIResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [selectedVisualization, setSelectedVisualization] = useState<{ index: number; visual: VisualRecommendation } | null>(null);
  const [analysisDuration, setAnalysisDuration] = useState<number | null>(null);
  const [copiedCode, setCopiedCode] = useState<number | null>(null);

  useEffect(() => {
    if (location.state?.fileId) {
      setFileId(location.state.fileId);
    }
  }, [location.state]);

  useEffect(() => {
    const loadKpis = async () => {
      if (!fileId) {
        setFileInfo(null);
        setKpiData(null);
        setAnalysisDuration(null);
        return;
      }

      setLoading(true);
      const startTime = performance.now();
      try {
        const [file, kpis] = await Promise.all([
          fileService.getFile(fileId),
          fileService.getFileKpis(fileId),
        ]);
        const endTime = performance.now();
        const duration = endTime - startTime;
        
        setFileInfo(file);
        setKpiData(kpis);
        setAnalysisDuration(duration);
      } catch (error) {
        console.error('Error loading KPI dashboard:', error);
        setAnalysisDuration(null);
      } finally {
        setLoading(false);
      }
    };

    loadKpis();
  }, [fileId]);

  const handleFileUploaded = (file: UploadedFile) => {
    setFileId(file.id);
    setFileInfo(file);
  };

  const handleCopyCode = (code: string, index: number) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(index);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const validVisualRecommendations =
    kpiData?.visual_recommendations?.filter((visual) => Boolean(visual.chart_data?.data?.data?.length)) ?? [];

  const shouldShowFallbackCharts =
    !loading && Boolean(kpiData?.charts?.length) && validVisualRecommendations.length === 0;

  return (
    <div className="h-screen flex flex-col bg-gray-50">
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
              <FileSpreadsheet className="w-6 h-6 text-primary-600" />
              <div>
                <h1 className="text-xl font-bold text-gray-900">KPI Dashboard</h1>
                {fileInfo ? (
                  <p className="text-sm text-gray-600">
                    {fileInfo.original_filename} ({fileInfo.row_count} rows)
                  </p>
                ) : (
                  <p className="text-sm text-gray-600">Upload a file to see KPI insights</p>
                )}
              </div>
            </div>
            {fileId && (
              <button
                onClick={() => navigate('/chat', { state: { fileId } })}
                className="btn-secondary text-sm"
                title="Chat feature is currently in beta"
              >
                Switch to Chat (Beta)
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-hidden flex">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-7xl mx-auto space-y-6">
            {!fileId && (
              <div className="rounded-3xl border border-dashed border-gray-300 bg-white p-10 text-center">
                <h2 className="text-2xl font-semibold text-gray-900 mb-4">Upload your data</h2>
                <p className="text-gray-600 mb-6">
                  Choose your CSV or Excel file and then view the KPI dashboard.
                </p>
                <FileUpload onFileUploaded={handleFileUploaded} />
              </div>
            )}

            {fileId && (
              <div className="space-y-6">
                <div className="rounded-3xl bg-white p-6 shadow-sm border border-gray-200">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div>
                      <h2 className="text-3xl font-bold text-gray-900">Executive KPI Dashboard</h2>
                      <p className="text-gray-600 mt-2 max-w-2xl">
                        This summary is designed for fast decisions: clear metrics, trusted status indicators, and visual insights in one view.
                      </p>
                    </div>
                    <div className="flex flex-col sm:flex-row gap-3">
                      <button
                        onClick={() => navigate('/chat', { state: { fileId } })}
                        className="btn-secondary text-sm"
                        title="Chat feature is currently in beta"
                      >
                        Chat with Data (Beta)
                      </button>
                      <button
                        onClick={() => window.location.reload()}
                        className="btn-primary text-sm"
                      >
                        Refresh Dashboard
                      </button>
                    </div>
                  </div>
                </div>

                {loading && (
                  <div className="rounded-3xl bg-white p-6 shadow-sm border border-gray-200 text-gray-600">
                    <div className="flex items-center gap-3">
                      <Loader className="w-5 h-5 animate-spin" />
                      <span>Loading KPI insights...</span>
                    </div>
                  </div>
                )}

                {!loading && kpiData && (
                  <>
                    <div className="grid gap-4 xl:grid-cols-12">
                      {/* LEFT COLUMN: Main Charts & Visualizations */}
                      <div className="xl:col-span-8 space-y-4">
                        {shouldShowFallbackCharts && (
                          <div className="rounded-3xl bg-white border border-gray-200 shadow-sm p-6 lg:p-8">
                            <div className="mb-6 pb-5 border-b border-gray-200">
                              <h3 className="text-2xl font-bold text-gray-900">Dashboard Charts</h3>
                              <p className="text-gray-600 mt-2">AI chart recommendations were unavailable, so these standard dataset views are shown instead.</p>
                            </div>
                            <div className="grid gap-6 grid-cols-1 2xl:grid-cols-2">
                              {kpiData.charts.map((chart, idx) => (
                                <div key={idx} className="rounded-3xl overflow-hidden border border-gray-200 bg-gray-50 shadow-sm">
                                  <div className="bg-white px-5 py-4 border-b border-gray-200">
                                    <p className="font-semibold text-gray-900">{chart.title}</p>
                                  </div>
                                  <div className="p-4 bg-white">
                                    <Plot
                                      data={enhanceChartData(chart.data.data)}
                                      layout={enhanceChartLayout(chart.data.layout)}
                                      config={getProfessionalChartConfig()}
                                      className="w-full"
                                      style={{ width: '100%', height: '360px' }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {validVisualRecommendations.length > 0 && (
                          <div className="rounded-3xl bg-gradient-to-br from-white to-gray-50 border border-gray-200 shadow-sm p-6 lg:p-8">
                            <div className="mb-8 pb-6 border-b border-gray-200">
                              <div className="flex items-center gap-3 mb-3">
                                <div className="w-1 h-8 bg-gradient-to-b from-primary-600 to-primary-400 rounded-full"></div>
                                <h3 className="text-3xl font-bold bg-gradient-to-r from-primary-600 to-primary-700 bg-clip-text text-transparent">
                                  Recommended Visualizations
                                </h3>
                              </div>
                              <p className="text-gray-600 ml-4">✨ AI-powered chart recommendations to uncover key insights from your data</p>
                            </div>
                            <div className="grid gap-6 grid-cols-1 2xl:grid-cols-2">
                              {validVisualRecommendations.map((visual, idx) => (
                                <div
                                  key={idx}
                                  onClick={() => setSelectedVisualization({ index: idx, visual })}
                                  className="rounded-3xl border border-gray-200 bg-white overflow-hidden cursor-pointer hover:shadow-2xl hover:border-primary-400 hover:scale-105 transition-all duration-300 group shadow-lg"
                                >
                                  {/* Gradient accent line */}
                                  <div className="h-1 bg-gradient-to-r from-primary-600 via-primary-500 to-primary-400"></div>
                                  
                                  <div className="bg-gradient-to-br from-slate-900 to-slate-800 px-6 py-5">
                                    <div className="flex items-center justify-between">
                                      <div className="flex-1">
                                        <p className="font-bold text-white text-lg group-hover:text-primary-300 transition-colors">
                                          {visual.title}
                                        </p>
                                      </div>
                                      <div className="flex items-center gap-3 ml-4">
                                        <span className="text-xs uppercase tracking-[0.2em] text-primary-300 font-bold px-3 py-1 bg-primary-600/30 rounded-full">
                                          AI Insight
                                        </span>
                                        <Maximize2 className="w-5 h-5 text-primary-300 opacity-0 group-hover:opacity-100 group-hover:scale-110 transition-all" />
                                      </div>
                                    </div>
                                  </div>
                                  <div className="p-6">
                                    <p className="text-sm text-gray-700 mb-5 leading-relaxed">{visual.description}</p>
                                    
                                    {/* Generated Code Section */}
                                    {visual.generated_code && (
                                      <div className="rounded-2xl bg-gradient-to-br from-slate-950 to-slate-900 p-4 border border-slate-700 mb-5 shadow-lg">
                                        <div className="flex items-center justify-between mb-3">
                                          <p className="text-xs uppercase tracking-wider text-slate-400 font-bold">🐍 Generated Pandas Code</p>
                                          <button
                                            onClick={() => handleCopyCode(visual.generated_code ?? '', idx)}
                                            className="p-1.5 hover:bg-slate-800 rounded transition-colors"
                                            title="Copy code to clipboard"
                                          >
                                            {copiedCode === idx ? (
                                              <Check className="w-4 h-4 text-emerald-400" />
                                            ) : (
                                              <Copy className="w-4 h-4 text-slate-400" />
                                            )}
                                          </button>
                                        </div>
                                        <pre className="text-xs text-emerald-400 font-mono overflow-x-auto max-h-48 p-3 bg-slate-900/50 rounded border border-slate-800">
                                          {visual.generated_code}
                                        </pre>
                                        <p className="text-xs text-slate-500 mt-3 italic">
                                          📋 Automatically generated by DeepSeek to create this visualization
                                        </p>
                                      </div>
                                    )}
                                    
                                    {/* Suggested Query Section */}
                                    <div className="rounded-2xl bg-gradient-to-br from-slate-950 to-slate-900 p-4 border border-slate-700 mb-5 shadow-lg">
                                      <p className="text-xs uppercase tracking-wider text-slate-400 mb-3 font-bold">📝 Suggested Query</p>
                                      <p className="text-sm text-emerald-400 font-mono break-words whitespace-normal leading-relaxed text-opacity-90">
                                        {visual.suggested_query}
                                      </p>
                                      <p className="text-xs text-slate-500 mt-3 italic">
                                        💡 Use this query to customize the visualization
                                      </p>
                                    </div>
                                    {visual.chart_data ? (
                                      <div className="rounded-3xl bg-white p-4 border border-gray-200 shadow-inner">
                                        <Plot
                                          data={enhanceChartData(visual.chart_data.data.data)}
                                          layout={enhanceChartLayout(visual.chart_data.data.layout)}
                                          config={getProfessionalChartConfig()}
                                          className="w-full"
                                          style={{ width: '100%', height: '420px' }}
                                        />
                                      </div>
                                    ) : (
                                      <div className="rounded-2xl bg-gray-50 p-8 border border-dashed border-gray-300 text-center text-sm text-gray-500">
                                        <p className="font-medium mb-1">Chart could not be generated</p>
                                        <p>Try refining the suggested query or check your data</p>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* RIGHT COLUMN: Sidebar Reports */}
                      <aside className="xl:col-span-4 space-y-4">
                        
                        <div className="rounded-3xl bg-white p-6 border border-gray-200 shadow-sm">
                          <div className="flex items-center justify-between gap-4 mb-5">
                            <div>
                              <p className="text-xs uppercase tracking-[0.25em] text-gray-500">Report</p>
                              <h3 className="text-xl font-semibold text-gray-900">Snapshot</h3>
                            </div>
                            <span className="text-xs uppercase tracking-[0.2em] text-primary-600 font-semibold">Live</span>
                          </div>
                          <div className="space-y-4">
                            <div className="rounded-3xl bg-slate-50 p-4 border border-slate-200">
                              <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Source</p>
                              <p className="mt-2 text-sm text-gray-700">{fileInfo?.original_filename || 'Uploaded file'}</p>
                            </div>
                            <div className="rounded-3xl bg-slate-50 p-4 border border-slate-200">
                              <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Last refreshed</p>
                              <p className="mt-2 text-sm text-gray-700">{fileInfo?.upload_date ? new Date(fileInfo.upload_date).toLocaleString() : 'Just now'}</p>
                            </div>
                            <div className="rounded-3xl bg-slate-50 p-4 border border-slate-200">
                              <p className="text-xs uppercase tracking-[0.2em] text-gray-500">Rows</p>
                              <p className="mt-2 text-sm text-gray-700">{kpiData.summary.rows.toLocaleString()}</p>
                            </div>
                            {analysisDuration !== null && (
                              <div className="rounded-3xl bg-gradient-to-br from-primary-50 to-primary-100 p-4 border border-primary-200 shadow-sm">
                                <p className="text-xs uppercase tracking-[0.2em] text-primary-700 font-semibold">⚡ Analysis Time</p>
                                <p className="mt-2 text-lg font-bold text-primary-700">
                                  {analysisDuration < 1000 
                                    ? `${Math.round(analysisDuration)}ms` 
                                    : `${(analysisDuration / 1000).toFixed(2)}s`}
                                </p>
                                <p className="text-xs text-primary-600 mt-1">
                                  {analysisDuration < 1000 ? 'Lightning fast!' : 'Generated in seconds'}
                                </p>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* UPDATED: Analysis Insights Layout */}
                        {kpiData.analysis_insights && kpiData.analysis_insights.length > 0 && (
                          <div className="rounded-3xl bg-white border border-gray-200 shadow-sm p-6">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Analysis Insights</h3>
                            <div className="space-y-5">
                              {kpiData.analysis_insights.map((insight, idx) => (
                                <div key={idx} className="rounded-3xl bg-slate-50 p-5 border border-slate-200">
                                  <h4 className="font-semibold text-gray-900 mb-2">{insight.title}</h4>
                                  <p className="text-sm text-gray-600 mb-4">{insight.description}</p>
                                  
                                  <div className="space-y-4"> {/* Changed to a vertical stack */}
                                    {insight.key_findings && insight.key_findings.length > 0 && (
                                      <div>
                                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500 mb-2">Key Findings</p>
                                        <ul className="space-y-1 text-sm text-gray-700">
                                          {insight.key_findings.map((finding, fidx) => (
                                            <li key={fidx}>• {finding}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                    {insight.recommendations && insight.recommendations.length > 0 && (
                                      <div>
                                        <p className="text-xs uppercase tracking-[0.2em] text-gray-500 mb-2">Recommendations</p>
                                        <ul className="space-y-1 text-sm text-gray-700">
                                          {insight.recommendations.map((rec, ridx) => (
                                            <li key={ridx}>• {rec}</li>
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {kpiData.data_quality && kpiData.data_quality.length > 0 && (
                          <div className="rounded-3xl bg-white p-6 border border-gray-200 shadow-sm">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Status Indicators</h3>
                            <div className="space-y-3">
                              {kpiData.data_quality.map((insight, idx) => {
                                const statusClasses =
                                  insight.status === 'good'
                                    ? 'bg-emerald-50 text-emerald-700 border-emerald-100'
                                    : insight.status === 'warning'
                                    ? 'bg-amber-50 text-amber-700 border-amber-100'
                                    : 'bg-rose-50 text-rose-700 border-rose-100';
                                return (
                                  <div key={idx} className={`rounded-2xl border p-4 ${statusClasses}`}>
                                    <p className="text-sm font-semibold">{insight.metric}</p>
                                    <p className="text-sm text-slate-700 mt-1">{insight.description}</p>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {kpiData.key_metrics && kpiData.key_metrics.length > 0 && (
                          <div className="rounded-3xl bg-white p-6 border border-gray-200 shadow-sm">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">Actionable Metrics</h3>
                            <ul className="space-y-3 text-sm text-gray-700">
                              {kpiData.key_metrics.map((metric, idx) => (
                                <li key={idx} className="rounded-2xl bg-gray-50 p-3 border border-gray-200">{metric}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </aside>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Zoom Modal for Visualizations */}
        {selectedVisualization && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-2xl max-w-6xl w-full max-h-[90vh] overflow-y-auto shadow-2xl">
              {/* Modal Header */}
              <div className="sticky top-0 bg-gradient-to-r from-primary-600 to-primary-700 p-6 flex items-center justify-between border-b border-primary-800 z-10">
                <div className="flex-1">
                  <h2 className="text-2xl font-bold text-white">{selectedVisualization.visual.title}</h2>
                  <p className="text-blue-100 mt-1">{selectedVisualization.visual.description}</p>
                </div>
                <button
                  onClick={() => setSelectedVisualization(null)}
                  className="p-2 hover:bg-primary-600 rounded-lg transition-colors ml-4 flex-shrink-0"
                >
                  <X className="w-6 h-6 text-white" />
                </button>
              </div>

              {/* Modal Content */}
              <div className="p-8">
                <div className="grid gap-8">
                  {/* Suggested Query Box */}
                  {/* Generated Code Section */}
                  {selectedVisualization.visual.generated_code && (
                    <div className="rounded-2xl bg-slate-900 p-6 border border-slate-700">
                      <div className="flex items-center justify-between mb-4">
                        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">🐍 Generated Pandas Code</p>
                        <button
                          onClick={() => handleCopyCode(selectedVisualization.visual.generated_code ?? '', -1)}
                          className="p-1.5 hover:bg-slate-800 rounded transition-colors"
                          title="Copy code to clipboard"
                        >
                          {copiedCode === -1 ? (
                            <Check className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Copy className="w-4 h-4 text-slate-400" />
                          )}
                        </button>
                      </div>
                      <pre className="text-xs text-emerald-400 font-mono overflow-x-auto max-h-64 p-4 bg-slate-800/50 rounded border border-slate-700">
                        {selectedVisualization.visual.generated_code}
                      </pre>
                      <p className="text-xs text-slate-500 mt-4">Automatically generated by DeepSeek to create this visualization</p>
                    </div>
                  )}

                  {/* Suggested Query Section */}
                  <div className="rounded-2xl bg-slate-900 p-6 border border-slate-700">
                    <p className="text-xs uppercase tracking-wider text-slate-400 mb-4 font-semibold">Suggested query (Development)</p>
                    <p className="text-sm text-emerald-400 font-mono break-words whitespace-normal leading-relaxed">
                      {selectedVisualization.visual.suggested_query}
                    </p>
                    <p className="text-xs text-slate-500 mt-4">Use this query to test chart generation or customize the visualization</p>
                  </div>

                  {/* Chart */}
                  {selectedVisualization.visual.chart_data ? (
                    <div className="rounded-2xl bg-white border border-gray-200 overflow-hidden shadow-lg">
                      <div className="p-8 bg-gradient-to-b from-gray-50 to-white">
                        <Plot
                          data={enhanceChartData(selectedVisualization.visual.chart_data.data.data)}
                          layout={enhanceChartLayout(selectedVisualization.visual.chart_data.data.layout)}
                          config={getProfessionalChartConfig()}
                          className="w-full"
                          style={{ width: '100%', height: '600px' }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="rounded-2xl bg-gray-50 p-12 border border-dashed border-gray-300 text-center">
                      <p className="font-medium text-gray-700 mb-2">Chart could not be generated</p>
                      <p className="text-sm text-gray-600">Try refining the suggested query or check your data</p>
                    </div>
                  )}

                  {/* Close Button */}
                  <div className="flex justify-end">
                    <button
                      onClick={() => setSelectedVisualization(null)}
                      className="btn-secondary px-6"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}