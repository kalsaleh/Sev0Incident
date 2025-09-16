import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';
import { Upload, FileSpreadsheet, Download, Eye, Trash2, BarChart3, Building2, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { Button } from './components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Input } from './components/ui/input';
import { Label } from './components/ui/label';
import { Progress } from './components/ui/progress';
import { Badge } from './components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './components/ui/table';
import { Alert, AlertDescription } from './components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './components/ui/tabs';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [batches, setBatches] = useState([]);
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [results, setResults] = useState([]);
  const [progress, setProgress] = useState({});
  const [loading, setLoading] = useState(false);

  const fetchAllCompanies = async () => {
    try {
      const response = await axios.get(`${API}/companies`);
      const companies = response.data;
      
      // Group companies by batch_id to create batches
      const batchMap = {};
      companies.forEach(company => {
        const batchId = company.batch_id || 'unknown';
        if (!batchMap[batchId]) {
          batchMap[batchId] = {
            batch_id: batchId,
            companies: [],
            total_companies: 0,
            status: 'completed',
            uploaded_at: company.created_at
          };
        }
        batchMap[batchId].companies.push(company);
        batchMap[batchId].total_companies++;
        
        // Determine batch status
        if (company.status === 'pending' || company.status === 'analyzing') {
          batchMap[batchId].status = 'processing';
        }
      });
      
      setBatches(Object.values(batchMap).sort((a, b) => 
        new Date(b.uploaded_at) - new Date(a.uploaded_at)
      ));
    } catch (error) {
      console.error('Error fetching companies:', error);
    }
  };

  // Load existing companies on startup
  useEffect(() => {
    fetchAllCompanies();
  }, []);

  // Poll for progress updates
  useEffect(() => {
    const interval = setInterval(() => {
      batches.forEach(batch => {
        if (batch.status !== 'completed') {
          fetchProgress(batch.batch_id);
        }
      });
    }, 2000);

    return () => clearInterval(interval);
  }, [batches]);

  const handleFileChange = (event) => {
    const selectedFile = event.target.files[0];
    if (selectedFile && selectedFile.type === 'text/csv') {
      setFile(selectedFile);
    } else {
      toast.error('Please select a valid CSV file');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      toast.error('Please select a CSV file first');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      console.log('Uploading file to:', `${API}/analyze-csv`);
      const response = await axios.post(`${API}/analyze-csv`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      console.log('Upload response:', response.data);

      const newBatch = {
        batch_id: response.data.batch_id,
        total_companies: response.data.total_companies,
        message: response.data.message,
        status: 'processing',
        uploaded_at: new Date().toISOString()
      };

      setBatches(prev => [newBatch, ...prev]);
      setFile(null);
      
      // Reset file input
      const fileInput = document.getElementById('csv-file');
      if (fileInput) fileInput.value = '';
      
      toast.success(response.data.message);
      
      // Start polling for this batch immediately
      fetchProgress(response.data.batch_id);
      
    } catch (error) {
      console.error('Upload error:', error);
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to upload file';
      toast.error(errorMessage);
    } finally {
      setUploading(false);
    }
  };

  const fetchProgress = async (batchId) => {
    try {
      console.log('Fetching progress for batch:', batchId);
      const response = await axios.get(`${API}/progress/${batchId}`);
      console.log('Progress response:', response.data);
      
      setProgress(prev => ({
        ...prev,
        [batchId]: response.data
      }));

      // Update batch status
      setBatches(prev => prev.map(batch => 
        batch.batch_id === batchId 
          ? { ...batch, status: response.data.status }
          : batch
      ));
    } catch (error) {
      console.error('Progress fetch error:', error);
    }
  };

  const fetchResults = async (batchId) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/results/${batchId}`);
      setResults(response.data);
      setSelectedBatch(batchId);
      toast.success('Results loaded successfully');
    } catch (error) {
      console.error('Results fetch error:', error);
      toast.error('Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (batchId) => {
    try {
      const response = await axios.get(`${API}/export/${batchId}`, {
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `digital_native_analysis_${batchId}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      toast.success('Results exported successfully');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export results');
    }
  };

  const handleDeleteBatch = async (batchId) => {
    if (!window.confirm('Are you sure you want to delete this batch? This action cannot be undone.')) {
      return;
    }

    try {
      await axios.delete(`${API}/batch/${batchId}`);
      setBatches(prev => prev.filter(batch => batch.batch_id !== batchId));
      if (selectedBatch === batchId) {
        setSelectedBatch(null);
        setResults([]);
      }
      toast.success('Batch deleted successfully');
    } catch (error) {
      console.error('Delete error:', error);
      toast.error('Failed to delete batch');
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />;
      case 'processing':
        return <Clock className="h-5 w-5 text-blue-500" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-500" />;
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />;
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-green-600 bg-green-50';
    if (score >= 60) return 'text-yellow-600 bg-yellow-50';
    if (score >= 40) return 'text-orange-600 bg-orange-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100">
      {/* Header */}
      <header className="bg-white/90 backdrop-blur-sm border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center space-x-3">
            <div className="bg-indigo-600 p-2 rounded-lg">
              <BarChart3 className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Digital Native Analyzer</h1>
              <p className="text-sm text-gray-600">AI-powered company analysis for incident.io prospects</p>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Tabs defaultValue="upload" className="space-y-6">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="upload" className="flex items-center space-x-2">
              <Upload className="h-4 w-4" />
              <span>Upload & Analyze</span>
            </TabsTrigger>
            <TabsTrigger value="batches" className="flex items-center space-x-2">
              <FileSpreadsheet className="h-4 w-4" />
              <span>Analysis Batches</span>
            </TabsTrigger>
            <TabsTrigger value="results" className="flex items-center space-x-2">
              <Eye className="h-4 w-4" />
              <span>Results</span>
            </TabsTrigger>
          </TabsList>

          {/* Upload Tab */}
          <TabsContent value="upload" className="space-y-6">
            <Card className="border-2 border-dashed border-gray-300 hover:border-indigo-400 transition-colors">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Upload className="h-5 w-5" />
                  <span>Upload Company Data</span>
                </CardTitle>
                <CardDescription>
                  Upload a CSV file with company information. Required columns: name, domain. 
                  Optional: industry, founded_year, employee_count, location, description
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="csv-file">Select CSV File</Label>
                  <Input
                    id="csv-file"
                    type="file"
                    accept=".csv"
                    onChange={handleFileChange}
                    className="file:mr-4 file:px-4 file:py-2 file:rounded-full file:border-0 file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                  />
                </div>
                
                {file && (
                  <Alert className="bg-blue-50 border-blue-200">
                    <FileSpreadsheet className="h-4 w-4" />
                    <AlertDescription>
                      Selected file: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
                    </AlertDescription>
                  </Alert>
                )}

                <Button 
                  onClick={handleUpload} 
                  disabled={!file || uploading}
                  className="w-full bg-indigo-600 hover:bg-indigo-700"
                >
                  {uploading ? (
                    <>
                      <Clock className="mr-2 h-4 w-4 animate-spin" />
                      Uploading & Starting Analysis...
                    </>
                  ) : (
                    <>
                      <Upload className="mr-2 h-4 w-4" />
                      Upload & Analyze
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            {/* Info Cards */}
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="bg-gradient-to-br from-green-50 to-emerald-100 border-emerald-200">
                <CardHeader>
                  <CardTitle className="text-emerald-800">Digital Native Scoring</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-emerald-700">
                    AI analyzes companies based on founding year, industry type, business model, 
                    and technology adoption to determine digital native likelihood.
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-blue-50 to-cyan-100 border-cyan-200">
                <CardHeader>
                  <CardTitle className="text-cyan-800">incident.io Fit Analysis</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-cyan-700">
                    Evaluates companies for incident management needs based on engineering complexity, 
                    uptime requirements, and technical infrastructure.
                  </p>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Batches Tab */}
          <TabsContent value="batches" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Analysis Batches</CardTitle>
                <CardDescription>Track the progress of your company analysis batches</CardDescription>
              </CardHeader>
              <CardContent>
                {batches.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <FileSpreadsheet className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No analysis batches yet. Upload a CSV file to get started.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {batches.map((batch) => {
                      const batchProgress = progress[batch.batch_id];
                      return (
                        <Card key={batch.batch_id} className="bg-white border border-gray-200">
                          <CardContent className="p-6">
                            <div className="flex items-center justify-between mb-4">
                              <div className="flex items-center space-x-3">
                                {getStatusIcon(batch.status)}
                                <div>
                                  <h3 className="font-semibold text-gray-900">
                                    Batch {batch.batch_id.substring(0, 8)}
                                  </h3>
                                  <p className="text-sm text-gray-600">
                                    {batch.total_companies} companies • {new Date(batch.uploaded_at).toLocaleDateString()}
                                  </p>
                                </div>
                              </div>
                              
                              <div className="flex items-center space-x-2">
                                <Badge variant={batch.status === 'completed' ? 'default' : 'secondary'}>
                                  {batch.status}
                                </Badge>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => fetchResults(batch.batch_id)}
                                >
                                  <Eye className="h-4 w-4 mr-1" />
                                  View
                                </Button>
                                {batch.status === 'completed' && (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleExport(batch.batch_id)}
                                  >
                                    <Download className="h-4 w-4 mr-1" />
                                    Export
                                  </Button>
                                )}
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleDeleteBatch(batch.batch_id)}
                                  className="text-red-600 hover:text-red-700"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </div>
                            </div>
                            
                            {batchProgress && (
                              <div className="space-y-2">
                                <div className="flex justify-between text-sm">
                                  <span>Progress: {batchProgress.completed}/{batchProgress.total_companies}</span>
                                  <span>{batchProgress.progress_percentage.toFixed(1)}%</span>
                                </div>
                                <Progress value={batchProgress.progress_percentage} className="h-2" />
                                {batchProgress.failed > 0 && (
                                  <p className="text-sm text-red-600">{batchProgress.failed} failed</p>
                                )}
                              </div>
                            )}
                          </CardContent>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Results Tab */}
          <TabsContent value="results" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Analysis Results</CardTitle>
                <CardDescription>
                  {selectedBatch 
                    ? `Showing results for batch ${selectedBatch.substring(0, 8)}`
                    : 'Select a batch from the Batches tab to view results'
                  }
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 animate-spin mx-auto mb-4 text-gray-400" />
                    <p className="text-gray-600">Loading results...</p>
                  </div>
                ) : results.length === 0 ? (
                  <div className="text-center py-8 text-gray-500">
                    <Building2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No results to display. Select a batch to view analysis results.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Company</TableHead>
                          <TableHead>Domain</TableHead>
                          <TableHead>Industry</TableHead>
                          <TableHead>Digital Native</TableHead>
                          <TableHead>incident.io Fit</TableHead>
                          <TableHead>Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {results.map((company) => (
                          <TableRow key={company.id}>
                            <TableCell>
                              <div>
                                <div className="font-medium">{company.name}</div>
                                {company.founded_year && (
                                  <div className="text-sm text-gray-600">Founded {company.founded_year}</div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <a 
                                href={`https://${company.domain}`} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className="text-blue-600 hover:underline"
                              >
                                {company.domain}
                              </a>
                            </TableCell>
                            <TableCell>{company.industry || 'N/A'}</TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <Badge className={`${getScoreColor(company.digital_native_score)} px-2 py-1`}>
                                  {company.digital_native_score}%
                                </Badge>
                                <div className="text-xs text-gray-600">
                                  {company.is_digital_native ? '✓ Digital Native' : '✗ Not Digital Native'}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={`${getScoreColor(company.incident_io_fit_score)} px-2 py-1`}>
                                {company.incident_io_fit_score}%
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center space-x-1">
                                {getStatusIcon(company.status)}
                                <span className="text-sm capitalize">{company.status}</span>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

export default App;