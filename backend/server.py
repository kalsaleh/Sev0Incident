from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import pandas as pd
import asyncio
import json
import re
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import io
import tempfile

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Models
class CompanyAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    domain: str
    industry: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    digital_native_score: Optional[float] = None
    is_digital_native: Optional[bool] = None
    digital_native_reasoning: Optional[str] = None
    incident_io_fit_score: Optional[float] = None
    incident_io_fit_reasoning: Optional[str] = None
    status: str = "pending"  # pending, analyzing, completed, error
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    analyzed_at: Optional[datetime] = None

class CompanyAnalysisCreate(BaseModel):
    name: str
    domain: str
    industry: Optional[str] = None
    founded_year: Optional[int] = None
    employee_count: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None

class BatchAnalysisRequest(BaseModel):
    companies: List[CompanyAnalysisCreate]

class BatchAnalysisResponse(BaseModel):
    batch_id: str
    total_companies: int
    message: str

class AnalysisProgress(BaseModel):
    batch_id: str
    total_companies: int
    completed: int
    failed: int
    progress_percentage: float
    status: str

# Initialize LLM Chat
def get_llm_chat():
    api_key = os.environ.get('EMERGENT_LLM_KEY')
    return LlmChat(
        api_key=api_key,
        session_id="digital-native-analyzer",
        system_message="""You are an expert business analyst specializing in identifying digital native companies and evaluating their fit for incident management tools.

Digital Native Company Criteria:
- Founded after 2010
- Cloud-native infrastructure and operations
- Heavy dependence on online/digital tools and platforms
- Primary business model involves digital products/services
- High technology adoption and integration
- Strong online presence and digital customer engagement

Incident.io Context:
incident.io provides AI-powered incident management platform for engineering teams, including:
- Real-time incident coordination and response
- On-call management and alerting
- AI-assisted incident resolution
- Post-incident analysis and reporting
- Integration with development and communication tools
- Service catalog and dependency mapping

Target customers are typically mid-to-large technology companies with complex software systems that require reliable incident management and operational resilience.

Your task is to analyze companies and provide:
1. Digital Native Score (0-100%): How likely the company is to be digital native
2. Incident.io Fit Score (0-100%): How likely they would need incident.io's services
3. Clear reasoning for both scores"""
    ).with_model("openai", "gpt-4o")

async def analyze_company_with_ai(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single company using AI"""
    try:
        chat = get_llm_chat()
        
        # Prepare company information
        company_info = f"""
Company Analysis Request:

Company Name: {company_data.get('name', 'N/A')}
Domain: {company_data.get('domain', 'N/A')}
Industry: {company_data.get('industry', 'N/A')}
Founded Year: {company_data.get('founded_year', 'N/A')}
Employee Count: {company_data.get('employee_count', 'N/A')}
Location: {company_data.get('location', 'N/A')}
Description: {company_data.get('description', 'N/A')}

Please analyze this company and provide:

**IMPORTANT CRITERIA FOR DIGITAL NATIVE:**
A company is digital native if it meets MOST of these criteria (not just founding year):
- Business model fundamentally depends on digital/online platforms
- Core product/service is software, SaaS, or digital
- Heavy reliance on technology infrastructure
- Born digital (even if before 2010, companies like Shopify, GitHub are digital native)
- Cloud-native or web-first approach
- Digital customer acquisition and engagement

**IMPORTANT CRITERIA FOR INCIDENT.IO FIT:**
A company needs incident.io if they have:
- Engineering teams managing complex software systems
- High uptime requirements (SaaS, e-commerce, fintech)
- Multiple services and microservices architecture  
- Need for incident response and on-call management
- DevOps/SRE practices
- Customer-facing digital services

**ANALYSIS REQUIRED:**

1. **Digital Native Score (0-100)**: Consider business model, not just founding year
   - Software/SaaS companies: Usually 70-100%
   - E-commerce platforms: Usually 60-90%  
   - Fintech: Usually 70-90%
   - Traditional companies with digital transformation: 20-60%
   - Pure traditional/physical companies: 0-30%

2. **Incident.io Fit Score (0-100)**: Based on technical complexity and uptime needs
   - SaaS/Cloud companies: Usually 60-90%
   - E-commerce platforms: Usually 50-80%
   - Fintech: Usually 70-90%
   - Traditional companies: Usually 10-40%

3. **Provide specific reasoning** explaining why the company is/isn't digital native and why they would/wouldn't need incident.io

**EXAMPLES:**
- Shopify (2006, E-commerce): HIGH digital native (85%+) - born digital, SaaS platform
- Stripe (2010, Fintech): HIGH digital native (90%+) - API-first, developer-focused
- MongoDB (2007, Database): HIGH digital native (80%+) - cloud database platform
- Traditional bank: LOW digital native (20%) - physical branches, traditional model

Format response as JSON:
{{
  "digital_native_score": <number>,
  "digital_native_reasoning": "<detailed explanation>",
  "incident_io_fit_score": <number>,
  "incident_io_fit_reasoning": "<detailed explanation>"
}}
"""

        message = UserMessage(text=company_info)
        response = await chat.send_message(message)
        
        # Parse JSON response
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate and normalize scores
                digital_score = float(result.get('digital_native_score', 0))
                incident_score = float(result.get('incident_io_fit_score', 0))
                
                return {
                    'digital_native_score': max(0, min(100, digital_score)),
                    'digital_native_reasoning': result.get('digital_native_reasoning', ''),
                    'incident_io_fit_score': max(0, min(100, incident_score)),
                    'incident_io_fit_reasoning': result.get('incident_io_fit_reasoning', ''),
                    'is_digital_native': digital_score >= 60
                }
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback scoring based on basic criteria
            return fallback_scoring(company_data)
            
    except Exception as e:
        logger.error(f"Error analyzing company {company_data.get('name', 'Unknown')}: {str(e)}")
        return fallback_scoring(company_data)

def fallback_scoring(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback scoring logic when AI analysis fails"""
    digital_score = 0
    incident_score = 0
    
    # Digital native scoring
    founded_year = company_data.get('founded_year')
    if founded_year and founded_year >= 2010:
        digital_score += 30
    
    industry = str(company_data.get('industry', '')).lower()
    digital_industries = ['saas', 'software', 'fintech', 'ecommerce', 'ai', 'technology', 'cloud', 'digital']
    if any(term in industry for term in digital_industries):
        digital_score += 40
    
    domain = str(company_data.get('domain', '')).lower()
    if any(ext in domain for ext in ['.ai', '.io', '.tech', '.app']):
        digital_score += 10
    
    # Incident.io fit scoring
    if digital_score >= 50:
        incident_score = digital_score * 0.8
    
    return {
        'digital_native_score': min(100, digital_score),
        'digital_native_reasoning': 'Automated scoring based on founding year, industry, and domain indicators.',
        'incident_io_fit_score': min(100, incident_score),
        'incident_io_fit_reasoning': 'Scoring based on digital native characteristics and likely technical complexity.',
        'is_digital_native': digital_score >= 60
    }

def enhanced_fallback_scoring(company_data: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced fallback scoring logic when AI analysis fails"""
    digital_score = 0
    incident_score = 0
    reasoning = []
    incident_reasoning = []
    
    name = company_data.get('name', '').lower()
    industry = str(company_data.get('industry', '')).lower()
    description = str(company_data.get('description', '')).lower()
    domain = str(company_data.get('domain', '')).lower()
    founded_year = company_data.get('founded_year')
    
    # Enhanced digital native scoring
    
    # High digital native industries (70-90 points)
    high_digital_industries = ['saas', 'software', 'fintech', 'ecommerce', 'e-commerce', 
                              'cloud', 'ai', 'machine learning', 'data', 'analytics', 
                              'platform', 'api', 'developer', 'tech', 'digital']
    if any(term in industry for term in high_digital_industries):
        digital_score += 70
        reasoning.append(f"High digital native industry: {industry}")
    else:
        # Medium digital native industries (40-60 points)
        medium_digital_industries = ['communication', 'social', 'media', 'marketing', 
                                    'automation', 'productivity', 'collaboration']
        if any(term in industry for term in medium_digital_industries):
            digital_score += 50
            reasoning.append(f"Medium digital native industry: {industry}")
    
    # Check description for digital indicators
    digital_keywords = ['platform', 'saas', 'cloud', 'api', 'software', 'digital', 
                       'online', 'web', 'app', 'service', 'technology', 'solution']
    digital_count = sum(1 for keyword in digital_keywords if keyword in description)
    if digital_count >= 3:
        digital_score += 20
        reasoning.append("Strong digital indicators in description")
    elif digital_count >= 1:
        digital_score += 10
        reasoning.append("Some digital indicators in description")
    
    # Domain analysis
    if any(ext in domain for ext in ['.io', '.ai', '.tech', '.app', '.dev']):
        digital_score += 10
        reasoning.append("Tech-focused domain extension")
    
    # Company name analysis
    tech_names = ['stripe', 'shopify', 'github', 'slack', 'zoom', 'datadog', 'mongodb']
    if any(tech_name in name for tech_name in tech_names):
        digital_score += 15
        reasoning.append("Well-known digital native company")
    
    # Founded year (less restrictive)
    if founded_year:
        if founded_year >= 2010:
            digital_score += 10
            reasoning.append(f"Founded in digital era ({founded_year})")
        elif founded_year >= 2000:
            digital_score += 5
            reasoning.append(f"Founded in early internet era ({founded_year})")
        else:
            reasoning.append(f"Founded before internet era ({founded_year})")
    
    # Incident.io fit scoring
    
    # High fit industries
    high_incident_industries = ['saas', 'fintech', 'ecommerce', 'cloud', 'platform', 'api']
    if any(term in industry for term in high_incident_industries):
        incident_score = min(90, digital_score * 0.8)
        incident_reasoning.append(f"High incident management needs for {industry} companies")
    elif digital_score >= 60:
        incident_score = min(80, digital_score * 0.7)
        incident_reasoning.append("Digital companies typically need incident management")
    else:
        incident_score = digital_score * 0.3
        incident_reasoning.append("Limited incident management needs for traditional companies")
    
    # Ensure scores are within bounds
    digital_score = min(100, max(0, digital_score))
    incident_score = min(100, max(0, incident_score))
    
    return {
        'digital_native_score': digital_score,
        'digital_native_reasoning': '; '.join(reasoning) if reasoning else 'Automated scoring based on industry and company characteristics',
        'incident_io_fit_score': incident_score,
        'incident_io_fit_reasoning': '; '.join(incident_reasoning) if incident_reasoning else 'Scoring based on digital native characteristics and likely technical complexity',
        'is_digital_native': digital_score >= 60
    }

async def process_batch_analysis(batch_id: str, companies: List[Dict[str, Any]]):
    """Process a batch of companies in the background"""
    try:
        for i, company_data in enumerate(companies):
            try:
                # Update status to analyzing
                await db.company_analyses.update_one(
                    {"id": company_data["id"]},
                    {"$set": {"status": "analyzing"}}
                )
                
                # Perform AI analysis
                analysis_result = await analyze_company_with_ai(company_data)
                
                # Update with analysis results
                update_data = {
                    **analysis_result,
                    "status": "completed",
                    "analyzed_at": datetime.now(timezone.utc)
                }
                
                await db.company_analyses.update_one(
                    {"id": company_data["id"]},
                    {"$set": update_data}
                )
                
                logger.info(f"Completed analysis for {company_data.get('name', 'Unknown')} ({i+1}/{len(companies)})")
                
            except Exception as e:
                logger.error(f"Error processing company {company_data.get('name', 'Unknown')}: {str(e)}")
                await db.company_analyses.update_one(
                    {"id": company_data["id"]},
                    {"$set": {"status": "error", "analyzed_at": datetime.now(timezone.utc)}}
                )
                
        logger.info(f"Batch {batch_id} processing completed")
        
    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {str(e)}")

# Routes
@api_router.get("/")
async def root():
    return {"message": "Digital Native Company Analyzer API"}

@api_router.post("/analyze-csv")
async def analyze_csv(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and analyze companies from CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Validate required columns
        required_columns = ['name', 'domain']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required columns: {missing_columns}"
            )
        
        # Convert DataFrame to company records
        companies = []
        batch_id = str(uuid.uuid4())
        
        for _, row in df.iterrows():
            company_data = {
                "id": str(uuid.uuid4()),
                "name": str(row.get('name', '')),
                "domain": str(row.get('domain', '')),
                "industry": str(row.get('industry', '')) if pd.notna(row.get('industry')) else None,
                "founded_year": int(row.get('founded_year')) if pd.notna(row.get('founded_year')) else None,
                "employee_count": str(row.get('employee_count', '')) if pd.notna(row.get('employee_count')) else None,
                "location": str(row.get('location', '')) if pd.notna(row.get('location')) else None,
                "description": str(row.get('description', '')) if pd.notna(row.get('description')) else None,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "batch_id": batch_id
            }
            companies.append(company_data)
        
        # Save to database
        if companies:
            await db.company_analyses.insert_many(companies)
            
            # Start background processing
            background_tasks.add_task(process_batch_analysis, batch_id, companies)
            
            return BatchAnalysisResponse(
                batch_id=batch_id,
                total_companies=len(companies),
                message=f"Started analysis of {len(companies)} companies"
            )
        else:
            raise HTTPException(status_code=400, detail="No valid companies found in CSV")
            
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

@api_router.get("/progress/{batch_id}")
async def get_progress(batch_id: str):
    """Get analysis progress for a batch"""
    total = await db.company_analyses.count_documents({"batch_id": batch_id})
    
    if total == 0:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    completed = await db.company_analyses.count_documents({
        "batch_id": batch_id, 
        "status": {"$in": ["completed", "error"]}
    })
    
    failed = await db.company_analyses.count_documents({
        "batch_id": batch_id, 
        "status": "error"
    })
    
    progress_percentage = (completed / total) * 100 if total > 0 else 0
    status = "completed" if completed == total else "processing"
    
    return AnalysisProgress(
        batch_id=batch_id,
        total_companies=total,
        completed=completed,
        failed=failed,
        progress_percentage=progress_percentage,
        status=status
    )

@api_router.get("/results/{batch_id}")
async def get_results(batch_id: str):
    """Get analysis results for a batch"""
    companies = await db.company_analyses.find({"batch_id": batch_id}).to_list(1000)
    
    if not companies:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return [CompanyAnalysis(**company) for company in companies]

@api_router.get("/export/{batch_id}")
async def export_results(batch_id: str):
    """Export results to Excel file"""
    companies = await db.company_analyses.find({"batch_id": batch_id}).to_list(1000)
    
    if not companies:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Convert to DataFrame
    df_data = []
    for company in companies:
        df_data.append({
            'Company Name': company.get('name'),
            'Domain': company.get('domain'),
            'Industry': company.get('industry'),
            'Founded Year': company.get('founded_year'),
            'Employee Count': company.get('employee_count'),
            'Location': company.get('location'),
            'Digital Native Score (%)': company.get('digital_native_score'),
            'Is Digital Native': company.get('is_digital_native'),
            'Digital Native Reasoning': company.get('digital_native_reasoning'),
            'Incident.io Fit Score (%)': company.get('incident_io_fit_score'),
            'Incident.io Fit Reasoning': company.get('incident_io_fit_reasoning'),
            'Analysis Status': company.get('status'),
            'Analyzed At': company.get('analyzed_at')
        })
    
    df = pd.DataFrame(df_data)
    
    # Create Excel file
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Digital Native Analysis', index=False)
        
        # Get the workbook and worksheet objects
        workbook = writer.book
        worksheet = writer.sheets['Digital Native Analysis']
        
        # Add formatting
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#4CAF50',
            'font_color': 'white',
            'border': 1
        })
        
        # Apply header formatting
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Auto-adjust column widths
        for i, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).str.len().max(),
                len(str(col))
            ) + 2
            worksheet.set_column(i, i, min(max_len, 50))
    
    output.seek(0)
    
    # Return as streaming response
    def iter_file():
        yield output.read()
    
    return StreamingResponse(
        io.BytesIO(output.getvalue()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=digital_native_analysis_{batch_id}.xlsx"}
    )

@api_router.get("/companies")
async def get_all_companies():
    """Get all analyzed companies with pagination"""
    companies = await db.company_analyses.find().sort("created_at", -1).to_list(100)
    return [CompanyAnalysis(**company) for company in companies]

@api_router.delete("/batch/{batch_id}")
async def delete_batch(batch_id: str):
    """Delete a batch and all its companies"""
    result = await db.company_analyses.delete_many({"batch_id": batch_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    return {"message": f"Deleted {result.deleted_count} companies from batch {batch_id}"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()