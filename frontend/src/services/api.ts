import axios from 'axios';
import type {
  GitHubIssue,
  PipelineResult,
  VerificationResult,
  PRAutomationResponse,
} from '../types/agent';

const API_BASE_URL = 'http://localhost:8000';


const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // triage/PR loop can legitimately take 20-40s; tune as needed
});

export const api = {
  fetchIssues: async (): Promise<{ issues: GitHubIssue[] }> => {
    const res = await client.get(`${API_BASE_URL}/api/issues`);
    return res.data;
  },

  runTriage: async (
    errorLog: string,
    sourceCodeContext: string
  ): Promise<PipelineResult> => {
    const res = await client.post(`${API_BASE_URL}/api/triage`, {
      error_log: errorLog,
      source_code_context: sourceCodeContext,
    });
    return res.data;
  },

  verifyPatch: async (
    targetFile: string,
    remediatedCode: string,
    testFileName: string,
    generatedTestCode: string
  ): Promise<VerificationResult> => {
    const res = await client.post(`${API_BASE_URL}/api/verify`, {
      target_file: targetFile,
      remediated_code: remediatedCode,
      test_file_name: testFileName,
      generated_test_code: generatedTestCode,
    });
    return res.data;
  },

  remediateAndPR: async (
    issueNumber: number,
    errorLog: string,
    sourceCodeContext: string
  ): Promise<PRAutomationResponse> => {
    const res = await client.post(`${API_BASE_URL}/api/remediate-and-pr`, {
      issue_number: issueNumber,
      error_log: errorLog,
      source_code_context: sourceCodeContext,
    });
    return res.data;
  },
};
