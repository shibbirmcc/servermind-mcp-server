# Workflow Prompt Improvements

## Summary

Enhanced the automated debugging workflow prompts to prevent workflow interruptions and ensure proper chain execution.

## Problem Identified

During debugging workflow execution, the `group_error_logs` step was interrupted because the AI assistant:
1. Analyzed the logs correctly ✅
2. Identified correlation IDs correctly ✅  
3. **Failed to format the required JSON response** ❌
4. **Used `attempt_completion` instead of continuing workflow** ❌

This broke the automated debugging chain at Step 4 of 9.

## Root Cause

The workflow prompts lacked sufficient emphasis on:
- **Workflow discipline** - staying within assigned role
- **Format compliance** - returning exact JSON structures
- **Chain continuation** - trusting the automated process

## Solution Implemented

Added consistent **Workflow Discipline Headers** to all workflow prompts:

### 🚨 WORKFLOW DISCIPLINE - CRITICAL INSTRUCTIONS
- Clear step identification (e.g., "Step 4 of 9")
- Role boundaries ("Your ONLY job is to...")
- Prohibition against premature conclusions
- Prohibition against using other tools
- Emphasis on exact JSON format compliance
- Trust in the automated process

### 📋 WORKFLOW CONTEXT
- Previous steps completed
- Current step identification  
- Next steps in the workflow
- Automatic trigger information

### 🔴 CRITICAL INSTRUCTIONS - NO EXCEPTIONS
- Specific formatting requirements
- Workflow continuation emphasis
- Chain breakage warnings
- Tool usage restrictions

## Files Updated

1. **`src/prompts/group_error_logs_prompt.txt`**
   - Step 4 of 9: Log grouping and ID extraction
   - Triggers: `splunk_trace_search_by_ids`

2. **`src/prompts/analyze_traces_narrative.txt`**
   - Step 6 of 9: Trace analysis and narrative building
   - Triggers: `root_cause_identification_prompt`

3. **`src/prompts/root_cause_identification_prompt.txt`**
   - Step 7 of 9: Root cause identification
   - Triggers: `ticket_split_prepare`

## Expected Impact

- **Prevents workflow interruptions** by emphasizing discipline
- **Ensures proper JSON formatting** with clear requirements
- **Maintains automated chain execution** through all 9 steps
- **Reduces debugging session failures** caused by premature conclusions
- **Improves consistency** across all workflow prompts

## Testing Recommendation

Test the complete debugging workflow end-to-end:
1. `logs_debug_entry` → `splunk_indexes` → `splunk_error_search` 
2. `group_error_logs` → `splunk_trace_search_by_ids` → `analyze_traces_narrative`
3. `root_cause_identification_prompt` → `ticket_split_prepare` → `automated_issue_creation`

Verify each step returns proper JSON plan structures and triggers the next step automatically.

## Future Maintenance

When adding new workflow prompts:
1. Include the **🚨 WORKFLOW DISCIPLINE** header
2. Add **📋 WORKFLOW CONTEXT** with step numbers
3. End with **🔴 CRITICAL INSTRUCTIONS** section
4. Emphasize JSON format compliance and chain continuation
5. Prohibit premature conclusions and tool switching

## Date
2025-08-17

## Related Issue
Debugging workflow interruption at `group_error_logs` step due to format non-compliance and premature `attempt_completion` usage.
