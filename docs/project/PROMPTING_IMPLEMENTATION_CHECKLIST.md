# Gweta Prompting Enhancement: Implementation Checklist

## Overview

This checklist guides the implementation of elite-level legal prompting for Gweta. Follow these steps to migrate from current prompts to enhanced Harvard Law-standard prompts.

---

## Phase 1: Preparation and Testing (Week 1)

### Day 1-2: Environment Setup

- [ ] **Review Enhanced Prompts**
  - [ ] Read `/api/composer/prompts_enhanced.py` completely
  - [ ] Understand key differences from current `prompts.py`
  - [ ] Review `/docs/project/PROMPTING_ENHANCEMENT_GUIDE.md` for philosophy

- [ ] **Set Up A/B Testing Infrastructure**
  ```python
  # Add to .env or environment
  USE_ENHANCED_PROMPTS=false  # Start with false for testing
  ENHANCED_PROMPTS_ROLLOUT_PERCENTAGE=0  # For gradual rollout
  ```

- [ ] **Create Testing Branch**
  ```bash
  git checkout -b feature/enhanced-legal-prompts
  ```

- [ ] **Update Token Limits in Settings**
  ```python
  # libs/common/settings.py
  # Increase max_tokens for enhanced prompts
  OPENAI_MAX_TOKENS_SIMPLE = 800      # was 500
  OPENAI_MAX_TOKENS_MODERATE = 2500   # was 1500
  OPENAI_MAX_TOKENS_COMPLEX = 5000    # was 3000
  OPENAI_MAX_TOKENS_EXPERT = 8000     # was 4000
  ```

### Day 3-4: Create Test Suite

- [ ] **Create Golden Dataset**
  ```python
  # tests/evaluation/golden_dataset.py
  GOLDEN_LEGAL_QUERIES = [
      {
          "id": "employment_001",
          "query": "Can employer dismiss without hearing?",
          "complexity": "moderate",
          "expected_authorities": ["Section 12 Labour Act", "Nyamande v Cold Comfort"],
          "min_citations": 3,
          "min_words": 600,
          "requires_adversarial_analysis": True
      },
      # Add 20-30 golden examples across different legal areas
  ]
  ```

- [ ] **Create Prompt Comparison Test**
  ```python
  # tests/api/composer/test_prompt_comparison.py
  
  @pytest.mark.asyncio
  async def test_enhanced_vs_original_prompts():
      """Compare enhanced prompts against original on golden dataset."""
      
      from api.composer.prompts import get_prompt_template as get_original
      from api.composer.prompts_enhanced import get_prompt_template as get_enhanced
      
      # Test both versions
      for query_data in GOLDEN_LEGAL_QUERIES:
          original_response = await invoke_with_prompts(query_data, get_original)
          enhanced_response = await invoke_with_prompts(query_data, get_enhanced)
          
          # Compare metrics
          compare_responses(original_response, enhanced_response, query_data)
  ```

- [ ] **Create Quality Metrics Tests**
  ```python
  # tests/api/composer/test_quality_metrics.py
  
  def test_citation_density():
      """Test citation density meets 85% threshold."""
      pass
      
  def test_analysis_depth():
      """Test presence of required analytical sections."""
      pass
      
  def test_confidence_calibration():
      """Test legal position confidence is stated."""
      pass
  ```

### Day 5: Baseline Testing

- [ ] **Run Current System Baseline**
  ```bash
  pytest tests/evaluation/test_golden_dataset.py --baseline
  ```
  - [ ] Record current metrics:
    - Average response length
    - Citation count
    - Citation density
    - Analysis depth score
    - Professional quality rating

- [ ] **Document Baseline Results**
  - [ ] Create `/tests/evaluation/baseline_results.json`
  - [ ] Include sample responses for comparison

---

## Phase 2: Side-by-Side Testing (Week 2)

### Day 6-7: Enable Enhanced Prompts in Test Environment

- [ ] **Create Feature Flag System**
  ```python
  # api/composer/prompt_selector.py
  
  import os
  from api.composer import prompts, prompts_enhanced
  
  def get_prompt_module():
      """Select prompt module based on feature flag."""
      if os.getenv("USE_ENHANCED_PROMPTS", "false").lower() == "true":
          return prompts_enhanced
      return prompts
  ```

- [ ] **Update Orchestrator to Use Feature Flag**
  ```python
  # api/orchestrators/query_orchestrator.py
  
  from api.composer.prompt_selector import get_prompt_module
  
  def _build_synthesis_prompt(self, state: AgentState) -> str:
      prompt_module = get_prompt_module()
      template = prompt_module.get_prompt_template(...)
      # ...
  ```

- [ ] **Add Enhanced Prompts Logging**
  ```python
  logger.info(
      "Synthesis prompt invoked",
      prompt_version="enhanced" if use_enhanced else "original",
      user_type=user_type,
      complexity=complexity,
      query_length=len(query)
  )
  ```

### Day 8-9: Run Comparison Tests

- [ ] **Enable Enhanced Prompts**
  ```bash
  export USE_ENHANCED_PROMPTS=true
  ```

- [ ] **Run Golden Dataset Tests**
  ```bash
  pytest tests/evaluation/test_golden_dataset.py --enhanced
  ```

- [ ] **Compare Results**
  - [ ] Response length (expect 2-3x increase)
  - [ ] Citation density (expect increase to >85%)
  - [ ] Analysis depth (expect all required sections present)
  - [ ] Token usage (expect 3-5x increase)
  - [ ] Cost per query (expect 3-5x increase)

- [ ] **Generate Comparison Report**
  ```bash
  python tests/evaluation/generate_comparison_report.py
  ```

### Day 10: Professional Review

- [ ] **Select Sample Responses**
  - [ ] Choose 10 responses from golden dataset
  - [ ] Include mix of simple, moderate, complex queries
  - [ ] Blind the samples (don't indicate which is enhanced)

- [ ] **Conduct Professional Review**
  - [ ] Share with 2-3 legal practitioners
  - [ ] Use review rubric from Enhancement Guide
  - [ ] Collect ratings and feedback

- [ ] **Analyze Feedback**
  - [ ] Identify patterns in quality improvements
  - [ ] Note any issues or concerns
  - [ ] Document specific examples of excellence

---

## Phase 3: Gradual Rollout (Week 3-4)

### Week 3: Professional Users + Complex Queries

- [ ] **Implement Selective Rollout Logic**
  ```python
  # api/composer/prompt_selector.py
  
  def should_use_enhanced_prompts(state: AgentState) -> bool:
      """Determine if enhanced prompts should be used."""
      
      # Feature flag check
      if not os.getenv("ENABLE_ENHANCED_PROMPTS", "false") == "true":
          return False
      
      # Start with professional users only
      if state.user_type != "professional":
          return False
      
      # Start with complex queries only
      if state.complexity not in ["complex", "expert"]:
          return False
      
      # Gradual percentage rollout
      rollout_pct = int(os.getenv("ENHANCED_PROMPTS_ROLLOUT_PCT", "0"))
      if rollout_pct < 100:
          user_hash = hash(state.user_id) % 100
          if user_hash >= rollout_pct:
              return False
      
      return True
  ```

- [ ] **Deploy to Staging**
  ```bash
  # Set environment variables
  export ENABLE_ENHANCED_PROMPTS=true
  export ENHANCED_PROMPTS_ROLLOUT_PCT=20  # Start with 20% of eligible users
  
  # Deploy
  git push staging feature/enhanced-legal-prompts
  ```

- [ ] **Monitor Key Metrics**
  - [ ] Average response time (expect slight increase)
  - [ ] Token usage per query (expect 3-5x for enhanced)
  - [ ] LLM API costs (monitor closely)
  - [ ] Error rates (should remain stable)
  - [ ] User satisfaction ratings (expect improvement)

- [ ] **Collect User Feedback**
  - [ ] Add feedback prompt: "How would you rate the depth of legal analysis?"
  - [ ] Monitor support tickets for quality issues
  - [ ] Conduct user interviews with professional users

### Week 4: Expand Rollout

- [ ] **Increase Rollout Percentage**
  - Day 1: 20% → 50%
  - Day 3: 50% → 80%
  - Day 5: 80% → 100% (for professional + complex)

- [ ] **Expand to Moderate Complexity**
  ```python
  if state.complexity in ["moderate", "complex", "expert"]:
      return True
  ```

- [ ] **Monitor Costs**
  - [ ] Track daily LLM API costs
  - [ ] Compare to baseline
  - [ ] Adjust rollout if costs exceed budget

- [ ] **Quality Assurance**
  - [ ] Spot check 20 responses per day
  - [ ] Verify citation accuracy
  - [ ] Check for any hallucinations
  - [ ] Confirm appropriate disclaimers

---

## Phase 4: Full Migration (Week 5-6)

### Week 5: Enable for All Users

- [ ] **Extend to Citizen Users**
  ```python
  # Now enable for all user types
  if state.user_type in ["professional", "citizen"]:
      if state.complexity != "simple":  # Keep simple queries efficient
          return True
  ```

- [ ] **Deploy to Production**
  ```bash
  # After successful staging validation
  git checkout main
  git merge feature/enhanced-legal-prompts
  git push origin main
  
  # Production deployment
  export ENABLE_ENHANCED_PROMPTS=true
  export ENHANCED_PROMPTS_ROLLOUT_PCT=100
  ```

- [ ] **Communication**
  - [ ] Update user documentation
  - [ ] Announce enhanced capabilities in changelog
  - [ ] Update marketing materials
  - [ ] Send email to professional users highlighting improvements

### Week 6: Cleanup and Optimization

- [ ] **Archive Old Prompts**
  ```bash
  git mv api/composer/prompts.py api/composer/prompts_legacy.py
  git mv api/composer/prompts_enhanced.py api/composer/prompts.py
  git commit -m "Migrate to enhanced prompts as default"
  ```

- [ ] **Remove Feature Flags**
  ```python
  # Remove conditional logic, enhanced prompts are now default
  # Keep legacy prompts for backward compatibility if needed
  ```

- [ ] **Update Tests**
  - [ ] Update all tests to expect enhanced prompt outputs
  - [ ] Update golden dataset expected values
  - [ ] Update baseline metrics

- [ ] **Documentation**
  - [ ] Update API documentation
  - [ ] Create prompt engineering guide for future enhancements
  - [ ] Document lessons learned

---

## Phase 5: Optimization and Refinement (Ongoing)

### Token Usage Optimization

- [ ] **Analyze Actual Token Usage**
  ```python
  # Create analytics query
  SELECT
      complexity,
      user_type,
      AVG(completion_tokens) as avg_tokens,
      MAX(completion_tokens) as max_tokens,
      P95(completion_tokens) as p95_tokens
  FROM
      llm_invocations
  WHERE
      prompt_version = 'enhanced'
  GROUP BY
      complexity, user_type
  ```

- [ ] **Adjust Token Limits**
  - [ ] Set limits to P95 + 20% buffer
  - [ ] Avoid over-allocation (wasted cost)
  - [ ] Ensure sufficient headroom for comprehensive analysis

### Prompt Refinement

- [ ] **Collect Edge Cases**
  - [ ] Identify queries where analysis is weak
  - [ ] Collect examples of hallucinations (if any)
  - [ ] Note patterns in user feedback

- [ ] **Iterative Improvement**
  - [ ] A/B test prompt variations
  - [ ] Refine specific sections (e.g., adversarial analysis)
  - [ ] Add few-shot examples for common patterns

- [ ] **Version Management**
  ```python
  # Add version tracking to prompts
  PROMPT_VERSION = "2.0.0"  # Semantic versioning
  
  # Log prompt version with each invocation
  logger.info("Synthesis invoked", prompt_version=PROMPT_VERSION)
  ```

### Quality Monitoring Dashboard

- [ ] **Create Metrics Dashboard**
  - Citation density over time
  - Average response length by complexity
  - Professional quality ratings
  - Cost per query trends
  - User satisfaction scores

- [ ] **Set Alerts**
  - Citation density drops below 80%
  - Error rate increases above baseline
  - Cost per query exceeds budget threshold
  - User satisfaction drops below 4.0/5.0

---

## Quality Assurance Checklist

### Before Each Phase

- [ ] **Legal Accuracy Verification**
  - [ ] Sample 20 responses
  - [ ] Verify all citations against source documents
  - [ ] Check for hallucinated authorities
  - [ ] Confirm legal conclusions are grounded

- [ ] **Citation Accuracy Audit**
  - [ ] Verify citation format correctness
  - [ ] Check section numbers are accurate
  - [ ] Confirm case names and citations match sources
  - [ ] Ensure no fabricated citations

- [ ] **Disclaimer Verification**
  - [ ] All advice-seeking queries have disclaimers
  - [ ] Disclaimers are appropriately prominent
  - [ ] High-stakes queries have urgent professional help warnings

### Rollback Criteria (Phase 3-4)

Immediately rollback if:

- [ ] **Critical Issues**
  - [ ] Fabricated citations detected
  - [ ] Legal accuracy errors in >1% of responses
  - [ ] Systematic hallucinations

- [ ] **Major Issues**
  - [ ] Citation density falls below 75%
  - [ ] Error rate increases by >50%
  - [ ] User satisfaction drops significantly
  - [ ] Cost overruns exceed 200% of budget

### Success Criteria for Next Phase

Proceed to next phase only if:

- [ ] **Quality Metrics Met**
  - [ ] Citation density ≥85%
  - [ ] Citation accuracy 100%
  - [ ] Professional quality rating ≥4.0/5.0
  - [ ] Analysis depth score ≥90%

- [ ] **Operational Metrics Met**
  - [ ] Error rate stable or decreased
  - [ ] Response time acceptable (P95 <10s)
  - [ ] Costs within budget (or approved increase)

- [ ] **User Feedback Positive**
  - [ ] No critical issues reported
  - [ ] Positive feedback from professional users
  - [ ] No increase in support tickets related to quality

---

## Cost Management

### Budget Tracking

- [ ] **Establish Baseline**
  - Current cost per query (professional): $______
  - Current cost per query (citizen): $______
  - Current monthly LLM spend: $______

- [ ] **Set Enhanced Costs Budget**
  - Expected cost per query (professional complex): $______
  - Expected cost per query (professional moderate): $______
  - Maximum acceptable monthly spend: $______
  - Trigger for cost review: $______

- [ ] **Monitor Daily**
  ```sql
  SELECT
      DATE(timestamp) as date,
      COUNT(*) as queries,
      SUM(cost_usd) as total_cost,
      AVG(cost_usd) as avg_cost_per_query,
      SUM(CASE WHEN prompt_version='enhanced' THEN 1 ELSE 0 END) as enhanced_queries
  FROM
      llm_invocations
  GROUP BY
      DATE(timestamp)
  ORDER BY
      date DESC
  ```

### Cost Mitigation Strategies (If Needed)

- [ ] **Implement Tiered Service**
  - Basic: Current prompts (free/low cost)
  - Premium: Enhanced prompts (higher cost, premium users)
  - Professional: Unlimited enhanced (subscription)

- [ ] **Optimize Token Usage**
  - Reduce system prompt verbosity without losing quality
  - Implement intelligent summarization of long contexts
  - Cache common framework explanations

- [ ] **Smart Routing**
  - Use enhanced prompts only where value is clear
  - Keep simple queries on efficient prompts
  - Route based on user subscription tier

---

## Communication Plan

### Internal Communication

- [ ] **Engineering Team**
  - [ ] Brief on enhanced prompts philosophy and architecture
  - [ ] Walkthrough of implementation approach
  - [ ] Training on monitoring and troubleshooting

- [ ] **Product Team**
  - [ ] Demo enhanced capabilities
  - [ ] Discuss pricing implications
  - [ ] Align on marketing messaging

- [ ] **Legal/Compliance Team**
  - [ ] Review enhanced disclaimers
  - [ ] Confirm legal advice boundaries maintained
  - [ ] Validate citation accuracy processes

### External Communication

- [ ] **Professional Users**
  - [ ] Email announcement of enhanced capabilities
  - [ ] Highlight: deeper analysis, adversarial thinking, practical guidance
  - [ ] Invite feedback and case studies

- [ ] **Citizen Users**
  - [ ] Blog post: "Gweta Now Provides Even More Detailed Legal Information"
  - [ ] Emphasize: more comprehensive, better citations, clearer explanations

- [ ] **Marketing**
  - [ ] Update homepage: "Harvard Law-Grade Legal Analysis"
  - [ ] Create case studies showing before/after
  - [ ] Update demo videos

---

## Success Metrics (Final Review)

### Quantitative Targets

- [ ] **Citation Density**: ≥85% achieved ✓
- [ ] **Citation Accuracy**: 100% verified ✓
- [ ] **Analysis Depth**: ≥90% have all required sections ✓
- [ ] **Response Comprehensiveness**: ≥85% rated complete by reviewers ✓

### Qualitative Targets

- [ ] **Professional Rating**: ≥80% rated "Sophisticated" or "Elite" ✓
- [ ] **Persuasiveness**: ≥75% rated "Persuasive" or better ✓
- [ ] **Practical Utility**: ≥85% rated "Useful" or better ✓
- [ ] **Writing Quality**: Law review submission standard ✓

### Business Metrics

- [ ] **User Satisfaction**: Increase by ≥15% ✓
- [ ] **Professional Retention**: Increase by ≥10% ✓
- [ ] **Premium Conversions**: Increase by ≥20% (if tiered pricing) ✓
- [ ] **Cost per Query**: Within approved budget ✓

---

## Timeline Summary

| Week | Phase | Key Activities | Success Criteria |
|------|-------|----------------|------------------|
| 1 | Preparation | Setup, testing infrastructure, baseline | Tests created, baseline recorded |
| 2 | Side-by-Side Testing | A/B comparison, professional review | Enhanced prompts show clear improvement |
| 3 | Rollout Start | Professional + complex queries, 20→100% | Quality maintained, positive feedback |
| 4 | Rollout Expansion | Add moderate complexity, expand users | Costs within budget, quality high |
| 5 | Full Migration | All users, all complexity levels | Successful production deployment |
| 6 | Cleanup | Archive old prompts, optimize | Documentation complete, optimized |
| Ongoing | Optimization | Refine prompts, monitor quality | Continuous improvement |

---

## Risk Mitigation

### Identified Risks

1. **Cost Overruns**
   - **Mitigation**: Gradual rollout, daily monitoring, tiered service if needed
   - **Contingency**: Rollback plan, cost caps, selective enabling

2. **Quality Regression**
   - **Mitigation**: Rigorous testing, professional review, quality gates
   - **Contingency**: Immediate rollback, root cause analysis

3. **User Confusion**
   - **Mitigation**: Clear communication, gradual introduction, documentation
   - **Contingency**: Enhanced support, FAQ, user education

4. **Technical Issues**
   - **Mitigation**: Feature flags, gradual rollout, comprehensive monitoring
   - **Contingency**: Rollback capability, debugging tools, failover to original prompts

---

## Post-Migration Review (Week 8)

- [ ] **Metrics Review**
  - [ ] Compare all metrics to baseline
  - [ ] Analyze trends over rollout period
  - [ ] Document quantitative improvements

- [ ] **Qualitative Assessment**
  - [ ] Collect user testimonials
  - [ ] Professional user interviews
  - [ ] Case studies of excellent outputs

- [ ] **Financial Analysis**
  - [ ] Total cost increase
  - [ ] Cost per query by segment
  - [ ] ROI analysis (if premium pricing implemented)

- [ ] **Lessons Learned**
  - [ ] What went well
  - [ ] What could be improved
  - [ ] Recommendations for future enhancements

- [ ] **Future Roadmap**
  - [ ] Identified areas for further improvement
  - [ ] Advanced features to develop
  - [ ] Research opportunities

---

## Appendix: Quick Commands

### Testing
```bash
# Run baseline tests
pytest tests/evaluation/ --baseline

# Run enhanced prompts tests
export USE_ENHANCED_PROMPTS=true
pytest tests/evaluation/ --enhanced

# Compare results
python tests/evaluation/compare_prompts.py
```

### Deployment
```bash
# Deploy to staging
git push staging feature/enhanced-legal-prompts

# Deploy to production (after validation)
git checkout main
git merge feature/enhanced-legal-prompts
git push origin main
```

### Monitoring
```bash
# Check current rollout status
curl https://api.gweta.com/internal/feature-flags | jq '.enhanced_prompts'

# View real-time metrics
curl https://api.gweta.com/internal/metrics/prompts | jq

# Check costs
python scripts/cost_analysis.py --date-range=7d
```

### Rollback
```bash
# Emergency rollback
export ENABLE_ENHANCED_PROMPTS=false

# Or set rollout percentage to 0
export ENHANCED_PROMPTS_ROLLOUT_PCT=0
```

---

**Ready to begin? Start with Phase 1, Day 1! **
