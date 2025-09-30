# Gweta Legal AI: Elite Prompting Enhancement Guide

## Executive Summary

This document explains the comprehensive enhancement of Gweta's prompting system to achieve **Harvard Law-grade legal analysis**. The enhanced prompts transform Gweta from a competent legal information system into an AI assistant capable of producing sophisticated legal analysis suitable for elite practitioners, judges, and legal scholars.

## Table of Contents

1. [Core Philosophy](#core-philosophy)
2. [Key Improvements](#key-improvements)
3. [Comparative Examples](#comparative-examples)
4. [Migration Strategy](#migration-strategy)
5. [Quality Metrics](#quality-metrics)
6. [Testing Framework](#testing-framework)

---

## Core Philosophy

### The Harvard Law Standard

Responses from Gweta should demonstrate:

1. **Analytical Depth**: Multi-layered reasoning that goes beyond surface-level answers
2. **Scholarly Rigor**: Precise terminology, sophisticated legal concepts, academic-level analysis
3. **Authority Mastery**: Deep understanding of legal hierarchy, precedent, and interpretive principles
4. **Persuasive Writing**: Clear, authoritative prose that builds logical arguments
5. **Adversarial Thinking**: Anticipation of counterarguments and alternative interpretations
6. **Policy Integration**: Understanding of practical implications and legislative intent
7. **Intellectual Honesty**: Clear signaling of certainty vs. uncertainty; acknowledgment of gaps

### Grounding ≠ Quotation

Enhanced prompts distinguish between:
- **Shallow grounding**: Mere citation of sources
- **Deep grounding**: Analytical extraction and application of legal principles from sources

Example:

❌ **Shallow**: "(Source: Section 56(1) Constitution) Everyone has right to life."

✅ **Deep**: "(Source: Section 56(1) Constitution of Zimbabwe - binding constitutional provision) Every person has the right to life. This fundamental right, being constitutionally entrenched, can only be limited in accordance with Sections 86 and 87 of the Constitution, and any such limitation must satisfy strict proportionality requirements as established by the Constitutional Court in Zim. Lawyers for Human Rights v Min. of Justice SC-15-2019."

---

## Key Improvements

### 1. Master Constitutional Prompt Enhancement

**Before**: Basic hierarchy awareness
```
The Constitution is supreme law. All laws must conform.
Legal hierarchy: Constitution > Acts > SIs > Case Law
```

**After**: Sophisticated hierarchy with authority evaluation
```
Constitution is supreme law with purposive interpretation requirement.
Legal hierarchy with binding nature:
- Constitutional Court interpretations: authoritative and binding on all
- Acts of Parliament: binding; later enactments impliedly repeal inconsistent earlier provisions
- Statutory Instruments: binding if intra vires; subject to ultra vires review
- Case Law: binding/persuasive by court level with ratio/obiter distinction

Authority evaluation required:
- Assess binding vs. persuasive nature
- Evaluate strength (unanimous/divided, clear/ambiguous)
- Check currency (overruled/distinguished/good law)
- Prefer reported over unreported judgments
```

### 2. Analytical Structure Enhancement

**Before**: Basic IRAC
```
1. Issue
2. Rule
3. Application
4. Conclusion
```

**After**: Comprehensive analytical framework
```
1. ISSUE IDENTIFICATION
   - Precise legal question(s)
   - Sub-issues and threshold considerations
   
2. LEGAL FRAMEWORK ESTABLISHMENT
   - Constitutional provisions with brief analysis
   - Statutory framework with hierarchy
   - Regulatory framework if applicable
   - Judicial interpretation with authority evaluation
   - Hierarchy resolution

3. AUTHORITY ANALYSIS (for each significant authority)
   - Full, precise citation
   - Authority level (binding/persuasive, current/superseded)
   - Ratio/principle extraction
   - Relevance explanation
   - Strength assessment

4. APPLICATION AND REASONING
   - Textual, purposive, contextual analysis
   - Precedent application with distinguishing
   - Constitutional conformity check
   - Multi-authority synthesis

5. ADVERSARIAL ANALYSIS
   - Counterarguments identification
   - Weakness acknowledgment
   - Alternative interpretations
   - Distinguishing factors
   - Reasoned response to objections

6. PRACTICAL IMPLICATIONS
   - Procedural considerations
   - Enforcement mechanisms
   - Available remedies
   - Strategic considerations
   - Risk assessment

7. CONCLUSION
   - Clear legal position
   - Confidence calibration
   - Qualifying factors
   - Further research needs
```

### 3. Citation Enhancement: From Simple to Analytical

**Before**: Basic citation
```
(Source: Labour Act [Chapter 28:01] Section 12)
```

**After**: Analytical citation
```
(Source: Section 12(3)(b) of the Labour Act [Chapter 28:01] - binding statutory provision, as amended by Labour Amendment Act 2015)

This provision is binding statutory authority establishing the employer's obligation to provide written notice. The requirement is mandatory ("shall"), not discretionary, as confirmed by the Supreme Court in Nyamande v Cold Comfort Farm Trust SC 78/2020, which held that failure to provide written notice renders the termination procedurally unfair regardless of substantive cause.
```

### 4. Writing Style Enhancement: From Competent to Elite

**Before**: Functional legal writing
```
According to the Constitution, everyone has the right to work. This right is protected under Section 64. Employers must respect this right.
```

**After**: Sophisticated legal prose
```
(Source: Section 64 of the Constitution of Zimbabwe - fundamental constitutional right) The Constitution enshrines the right to choose one's trade, occupation, or profession freely. This right, while not absolute, enjoys constitutional protection and can only be limited in accordance with the general limitations clause (Section 86) where such limitation is fair, reasonable, necessary, and justifiable in a democratic society. 

The Constitutional Court has interpreted this provision broadly to encompass not merely the right to choose an occupation but also protection against arbitrary deprivation of livelihood (Source: Commercial Farmers Union v Minister of Lands [2020] ZWCC 1 at para 67). Consequently, any statutory or administrative action that effectively denies a person the ability to pursue their chosen profession must satisfy strict proportionality review, with the onus on the state to justify the limitation.

From a practical standpoint, this constitutional protection provides a basis for challenging arbitrary professional licensing restrictions, discriminatory employment policies, or regulatory schemes that lack rational connection to a legitimate public objective.
```

### 5. Adversarial Analysis Integration

**New Addition**: Every complex analysis now includes adversarial review

Example:
```
**ADVERSARIAL ANALYSIS**:

The primary legal position established above—that the termination was procedurally unfair—could face the following counterarguments:

1. **Argument**: The employee's serious misconduct justified summary dismissal without procedural compliance.
   
   **Response**: While serious misconduct can constitute substantive cause for dismissal, the Labour Act makes clear that procedural fairness requirements apply regardless of the gravity of misconduct (Source: Section 12(9) Labour Act [Chapter 28:01]). The Supreme Court in Nyamande explicitly rejected the argument that serious misconduct excuses procedural non-compliance, stating that "procedure and substance are distinct requirements, both of which must be satisfied" (at para 23).

2. **Argument**: The employee waived his right to procedural fairness by not raising it at the time of dismissal.
   
   **Response**: Procedural fairness rights are statutory protections that cannot be waived by silence or inaction. The courts have consistently held that failure to object at the time does not constitute waiver of fundamental procedural protections (Source: Marondera Town Council v Mhandarume [2019] ZWSC 89 at para 15).

**Assessment**: The counterarguments, while superficially plausible, do not withstand doctrinal scrutiny given the clear statutory language and binding Supreme Court precedent. The primary legal position remains robust.
```

### 6. Confidence Calibration

**New Addition**: Clear signaling of legal certainty levels

Examples:
```
**Settled Law** (high confidence):
"This legal position is well-established and consistently applied by the Supreme Court across multiple decisions. There is no ambiguity or conflicting authority."

**Arguable Position** (moderate confidence):
"While the High Court has adopted this interpretation in two recent decisions, the Supreme Court has not yet addressed the question directly. Alternative interpretations are legally plausible, though less consistent with the statutory language."

**Uncertain/Novel Question** (low confidence):
"This question presents a novel issue of first impression in Zimbabwean law. While principles from [jurisdiction] provide persuasive guidance, there is no binding Zimbabwean authority directly on point. The analysis above represents the most plausible interpretation based on analogous provisions and constitutional principles, but the ultimate judicial resolution remains uncertain."
```

### 7. Policy Integration

**New Addition**: Practical and policy considerations integrated throughout

Example:
```
**PRACTICAL IMPLICATIONS**:

1. **Procedural Requirements**: Employers seeking to terminate employment must:
   - Provide written notice with specific grounds (minimum 3 days before hearing)
   - Conduct formal disciplinary hearing
   - Allow employee to respond and call witnesses
   - Issue written decision with reasons
   - Advise of appeal rights

2. **Strategic Considerations**: 
   - Employers facing termination disputes should review procedural compliance meticulously, as procedural defects often prove fatal to defense of unfair dismissal claims
   - Employees should document all procedural irregularities contemporaneously to support potential unfair dismissal claims
   - Settlement negotiations may be advisable where procedural non-compliance is clear, even if substantive cause exists

3. **Enforcement**: 
   - Unfair dismissal claims must be filed with Labour Court within 30 days (jurisdictional deadline)
   - Remedies include reinstatement or compensation (up to 24 months' salary)
   - Costs typically follow the event

4. **Risk Assessment**: 
   - High risk of adverse finding where procedural non-compliance is clear and admitted
   - Medium risk where employer claims emergency/serious misconduct exemption (likely to fail on precedent)
   - Low risk if full procedural compliance can be demonstrated
```

---

## Comparative Examples

### Example 1: Employment Law Query

**Query**: "Can my employer fire me without a hearing?"

#### Before (Original Prompts):
```
According to the Labour Act, employers must follow fair procedures when terminating employment. Section 12 of the Labour Act requires that employees be given a hearing before dismissal. This is a procedural requirement.

If you are dismissed without a hearing, this may constitute unfair dismissal. You can file a complaint with the Labour Court within 30 days.

(Sources: Labour Act [Chapter 28:01])

This information is for educational purposes only and does not constitute legal advice.
```

**Word count**: ~80 words | **Sophistication**: Basic | **Depth**: Shallow

#### After (Enhanced Prompts):
```
**ISSUE**: Whether an employer may lawfully terminate employment without conducting a disciplinary hearing, and the legal consequences of procedural non-compliance.

**LEGAL FRAMEWORK**:

(Source: Section 64 of the Constitution of Zimbabwe - fundamental right) The Constitution protects the right to choose one's trade or profession freely, which has been interpreted to include protection against arbitrary deprivation of livelihood. 

(Source: Sections 12(3), 12(4), and 12(9) of the Labour Act [Chapter 28:01] - binding statutory provisions) The Labour Act establishes comprehensive procedural fairness requirements for termination of employment:

- Section 12(3) requires employers to provide the employee with written notice of allegations and proposed disciplinary action
- Section 12(4) mandates that the employee be given reasonable opportunity to respond and state their case
- Section 12(9) explicitly provides that termination without following these procedures constitutes unfair dismissal

**AUTHORITY ANALYSIS**:

(Source: Nyamande v Cold Comfort Farm Trust SC 78/2020; [2020] ZWSC 23 at paras 22-27 - binding Supreme Court precedent) The Supreme Court has definitively held that procedural fairness is a mandatory requirement separate from and independent of substantive cause for dismissal. The Court stated:

"An employer cannot rely on the existence of substantive cause for dismissal to excuse non-compliance with procedural requirements. Procedure and substance are distinct requirements, both of which must be satisfied for a dismissal to be fair." (at para 23)

The Court further held that summary dismissal without a hearing, even for serious misconduct, violates statutory requirements and renders the dismissal procedurally unfair (at para 26).

(Source: Zimbabwe Banking Corporation v Mabheka [2019] ZWSC 45 at para 18 - binding Supreme Court precedent) The Supreme Court has held that procedural rights under the Labour Act cannot be waived by conduct or acquiescence; they are statutory protections that must be affirmatively provided by the employer.

**APPLICATION AND ANALYSIS**:

Based on the binding statutory framework and consistent Supreme Court precedent, the legal position is clear and well-established:

1. **Mandatory Hearing Requirement**: Employers must conduct a disciplinary hearing before terminating employment. This is not discretionary but mandatory ("shall").

2. **No Serious Misconduct Exception**: Even where an employee commits serious misconduct that would constitute substantive cause for dismissal, the employer must still follow procedural requirements. There is no emergency or serious misconduct exception to the hearing requirement.

3. **Procedural vs. Substantive Fairness**: These are distinct requirements. An employer with substantive cause for dismissal (valid reason) can still commit unfair dismissal by failing to follow procedure.

4. **Written Notice and Opportunity to Respond**: At minimum, the employee must receive:
   - Written notice of allegations (specific charges)
   - Reasonable time to prepare response (typically minimum 48 hours)
   - Formal hearing where employee can state their case and call witnesses
   - Written decision with reasons
   - Notification of appeal rights

**ADVERSARIAL ANALYSIS**:

An employer might argue that:
- The employee's conduct was so serious that it justified summary dismissal without formalities
- The employee effectively waived procedural rights by not objecting at the time
- Compliance would have been futile as the decision was inevitable

However, these arguments are foreclosed by binding Supreme Court precedent. Nyamande explicitly rejected the serious misconduct argument, and Mabheka rejected the waiver argument. The "futility" defense has been rejected as contrary to the statutory scheme's emphasis on dignified treatment of employees.

**PRACTICAL IMPLICATIONS**:

1. **For Employees**:
   - If dismissed without a hearing, you have strong grounds for unfair dismissal claim
   - File complaint with Labour Court within 30 days (strict jurisdictional deadline)
   - Document all procedural irregularities: dates, what notice you received, whether you were given opportunity to respond
   - Remedies include: reinstatement with back pay, or compensation up to 24 months' salary

2. **Strategic Considerations**:
   - Even if employer had valid reason for dismissal (substantive cause), procedural non-compliance makes dismissal unfair
   - Settlement negotiations often advisable as employers face significant risk
   - Consider whether you want reinstatement (relationship) or compensation (moving on)

3. **Urgency**: The 30-day filing deadline is jurisdictional and strictly enforced. Missing it bars your claim entirely.

**CONCLUSION**:

**Legal Position** (HIGH CONFIDENCE - Settled Law): No, your employer cannot lawfully fire you without a hearing. The Labour Act mandates procedural fairness, and the Supreme Court has consistently held that termination without a disciplinary hearing constitutes unfair dismissal, regardless of whether substantive cause for dismissal exists.

**Strength of Position**: This is settled law with clear statutory language and consistent binding Supreme Court precedent. There is no ambiguity or conflicting authority.

**Recommended Action**: Seek immediate legal advice from a qualified labour law practitioner to file an unfair dismissal claim within the 30-day deadline. Document all facts relating to your dismissal, including dates, communications, and circumstances.

---

This information is for educational purposes only and does not constitute legal advice. For help with your specific situation, please consult a qualified legal practitioner.
```

**Word count**: ~850 words | **Sophistication**: Elite | **Depth**: Comprehensive

#### Key Improvements Demonstrated:
1. ✅ Structured analytical framework (Issue → Framework → Analysis → Conclusion)
2. ✅ Precise citations with authority evaluation
3. ✅ Deep legal reasoning with ratio extraction from precedents
4. ✅ Adversarial analysis addressing counterarguments
5. ✅ Practical implications with strategic guidance
6. ✅ Confidence calibration ("HIGH CONFIDENCE - Settled Law")
7. ✅ Authoritative, scholarly writing style
8. ✅ Policy integration (dignity, worker protection)

---

### Example 2: Constitutional Law Query

**Query**: "Does the government have the right to restrict freedom of assembly?"

#### Before (Original Prompts):
```
The Constitution of Zimbabwe protects freedom of assembly in Section 58. However, this right is not absolute and can be limited.

Section 86 allows limitations on constitutional rights if they are fair, reasonable, necessary, and justifiable in a democratic society.

The government must justify any restrictions.

(Sources: Constitution of Zimbabwe, Sections 58, 86)
```

**Word count**: ~60 words | **Depth**: Surface-level

#### After (Enhanced Prompts):
```
**ISSUE**: Whether the government possesses constitutional authority to restrict the freedom of assembly, and if so, under what conditions and subject to what limitations.

**CONSTITUTIONAL FRAMEWORK**:

(Source: Section 58 of the Constitution of Zimbabwe - fundamental constitutional right) The Constitution enshrines the freedom of assembly and association as a fundamental right:

"Every person has the right to freedom of assembly and association, and the right not to assemble or associate with others." (Section 58(1))

This right protects peaceful assembly, marches, demonstrations, and picketing. It is one of the foundational democratic rights essential to participatory governance and political accountability.

(Source: Section 86 of the Constitution of Zimbabwe - general limitations clause) Constitutional rights are not absolute and may be limited, but only in accordance with stringent constitutional requirements:

"The rights and freedoms set out in this Chapter must be exercised reasonably and with regard for the rights and freedoms of other persons.

The rights and freedoms set out in this Chapter may be limited only in terms of a law of general application and to the extent that the limitation is fair, reasonable, necessary and justifiable in a democratic society based on openness, justice, human dignity, equality and freedom..." (Section 86(2))

(Source: Section 87 of the Constitution - non-derogable rights) Section 87 lists rights that cannot be limited under any circumstances. Freedom of assembly is not listed as non-derogable, confirming that it may be subject to limitation under Section 86.

**CONSTITUTIONAL INTERPRETATION**:

(Source: Zim. Lawyers for Human Rights v Minister of Justice SC-15-2019 at paras 45-52 - binding Constitutional Court interpretation) The Constitutional Court has established a rigorous proportionality test for limitations on fundamental rights:

1. **Legality**: Limitation must be "in terms of a law of general application" - not arbitrary executive action
2. **Legitimate Aim**: Must serve pressing and substantial objective (public safety, rights of others, etc.)
3. **Rational Connection**: Means chosen must rationally advance the legitimate objective
4. **Necessity**: Must be necessary (not merely convenient) - least restrictive means to achieve objective
5. **Proportionality Stricto Sensu**: Deleterious effects must not outweigh beneficial effects; balancing required
6. **Democratic Values**: Must be justifiable in a democratic society based on "openness, justice, human dignity, equality and freedom"

The Court emphasized that the onus is on the state to justify the limitation, and courts must apply "strict scrutiny" to limitations on fundamental political rights like freedom of assembly (at para 48).

(Source: Fadzayi Mahere v Minister of Home Affairs [2020] ZWCC 7 at paras 33-38) The Constitutional Court further clarified that:

- Blanket prohibitions on assembly are presumptively unconstitutional
- Content-based restrictions (prohibiting assembly based on message) face heightened scrutiny
- Time, place, manner restrictions may be permissible if content-neutral and narrowly tailored
- Advance notification requirements are permissible but cannot operate as prior restraint systems
- Security concerns alone do not justify blanket prohibitions; state must demonstrate specific, imminent threat

**APPLICATION AND ANALYSIS**:

Based on this constitutional framework and judicial interpretation:

**Yes, the government has constitutional authority to restrict freedom of assembly, but only subject to strict constitutional limitations:**

1. **Limitation Must Be Statutory**: Restrictions must be imposed "in terms of a law of general application." Executive action or administrative discretion without clear statutory authority is unconstitutional. The relevant statute in Zimbabwe is the Maintenance of Peace and Order Act [Chapter 11:23], which must itself comply with constitutional requirements.

2. **Proportionality Test Must Be Satisfied**: Any restriction must satisfy all elements of the proportionality test established by the Constitutional Court. The government bears the onus of justification.

3. **Content Neutrality**: Restrictions based on the content or message of the assembly (e.g., prohibiting political protest but allowing other gatherings) face strict scrutiny and are presumptively unconstitutional unless the government can demonstrate compelling justification.

4. **Narrow Tailoring**: Restrictions must be no broader than necessary. For example:
   - ✅ Constitutionally permissible: Time/place restrictions to manage traffic flow in specific area
   - ❌ Constitutionally impermissible: City-wide ban on all demonstrations for indefinite period

5. **No Prior Restraint System**: While advance notification requirements are permissible (allowing police to facilitate and provide security), they cannot operate as a prior restraint system where authorities have discretion to arbitrarily prohibit assemblies.

**COMPARATIVE CONTEXT**:

(Source: South African jurisprudence on Section 17 of South African Constitution - persuasive authority) South African courts have developed sophisticated freedom of assembly jurisprudence under a similar constitutional framework. Key principles include:

- Peaceful protest is a "precious right" in a democracy and courts must be vigilant to protect it
- Economic inconvenience does not justify prohibition
- State must take reasonable measures to facilitate assembly, not merely prohibit to avoid difficulty

While not binding, this jurisprudence is persuasive given the similarity of constitutional language and Zimbabwe's legal tradition.

**ADVERSARIAL ANALYSIS**:

The government might argue that:

**Argument 1**: Public safety requires broad discretion to prohibit assemblies that may turn violent.

**Response**: While public safety is a legitimate objective, the Constitutional Court has held that generalized security concerns do not satisfy the necessity requirement. The state must demonstrate specific, credible, imminent threat of violence that cannot be addressed through less restrictive means (e.g., police presence, conditions on assembly). Prohibiting all assemblies because some might turn violent fails the least-restrictive-means test.

**Argument 2**: The right to assembly must yield to the rights of others to freedom of movement and economic activity.

**Response**: While balancing is required, the Constitutional Court has emphasized that fundamental political rights like assembly enjoy heightened protection. Economic inconvenience alone does not justify prohibition. Reasonable time/place/manner restrictions can protect others' rights without prohibiting assembly entirely.

**Argument 3**: Political instability justifies extraordinary measures.

**Response**: The Constitution does not contain a general "political instability" exception to fundamental rights. Even the state of emergency provisions (Section 113) have strict requirements and limitations. Political instability cannot be invoked to create a parallel constitutional regime with diminished rights protection.

**PRACTICAL IMPLICATIONS**:

1. **For Citizens/Organizations Planning Assemblies**:
   - Constitutional right exists but reasonable advance notification to police is required (typically 5-7 days)
   - Notification is not a request for permission; it is informing police to facilitate
   - If police attempt to prohibit assembly, immediate constitutional challenge may be necessary
   - Peaceful assembly is protected; violence or property destruction is not

2. **Legal Strategy if Assembly Prohibited**:
   - Urgent Constitutional Court application for interim relief (assembly rights are time-sensitive)
   - Allege violation of Section 58 and failure to satisfy Section 86 proportionality test
   - Seek costs against government if prohibition is arbitrary

3. **For Government Officials**:
   - Recognize high constitutional bar for restrictions
   - Facilitate rather than prohibit where possible
   - If restriction necessary, must be narrowly tailored and fully justified
   - Blanket prohibitions almost certainly unconstitutional

**CONCLUSION**:

**Legal Position** (HIGH CONFIDENCE - Settled Constitutional Law):

Yes, the government has constitutional authority to restrict freedom of assembly, but this authority is **strictly limited** by the Constitution. Restrictions must:
1. Be imposed by law of general application (statutory authority)
2. Serve legitimate and pressing objective
3. Be rationally connected to that objective
4. Be necessary (least restrictive means)
5. Be proportionate (benefits outweigh detriments)
6. Be justifiable in a democratic society

The Constitutional Court applies strict scrutiny to limitations on freedom of assembly, and the onus is on the government to justify any restriction. Blanket prohibitions, content-based restrictions, and arbitrary executive action are presumptively unconstitutional.

**Confidence Calibration**: This is settled constitutional law with clear Constitutional Court precedent. While application to specific factual scenarios may raise arguable questions, the general framework is unambiguous.

**Practical Takeaway**: Freedom of assembly is a fundamental right with strong constitutional protection. The government's authority to restrict it is real but constrained. Citizens have robust constitutional grounds to challenge arbitrary or disproportionate restrictions.

---

This analysis is for informational purposes only and does not constitute legal advice. Consult a qualified legal practitioner for advice on your specific situation and to develop a legal strategy tailored to your circumstances.
```

**Word count**: ~1400 words | **Sophistication**: Elite constitutional analysis | **Depth**: Comprehensive

#### Key Improvements Demonstrated:
1. ✅ Sophisticated constitutional interpretation methodology
2. ✅ Detailed proportionality analysis with specific tests
3. ✅ Integration of binding Constitutional Court precedent with ratio extraction
4. ✅ Comparative law analysis (South African persuasive authority)
5. ✅ Adversarial analysis with government's likely arguments and responses
6. ✅ Practical implications for multiple stakeholders
7. ✅ Confidence calibration with clear statement of settled law
8. ✅ Writing at law review/judicial opinion level

---

## Migration Strategy

### Phase 1: Side-by-Side Comparison (Week 1-2)

1. **A/B Testing Setup**:
   ```python
   # In orchestrator
   use_enhanced_prompts = os.getenv("USE_ENHANCED_PROMPTS", "false") == "true"
   
   if use_enhanced_prompts:
       from api.composer.prompts_enhanced import get_prompt_template
   else:
       from api.composer.prompts import get_prompt_template
   ```

2. **Logging for Comparison**:
   - Log response length, citation count, analysis depth metrics
   - Track user satisfaction ratings
   - Monitor LLM costs (enhanced prompts require more tokens)

3. **Initial Testing**:
   - Test on golden dataset queries
   - Run through professional legal reviewer
   - Compare against current production outputs

### Phase 2: Gradual Rollout (Week 3-4)

1. **Start with Professional Users**:
   - Enable enhanced prompts for `user_type="professional"` first
   - Maintain current prompts for citizen users initially
   - Collect feedback from legal practitioners

2. **Complexity-Based Rollout**:
   - Enable for `complexity="complex"` and `complexity="expert"` first
   - Monitor quality and cost metrics
   - Extend to moderate complexity if successful

3. **Monitoring**:
   - Track average response time and token usage
   - Monitor citation accuracy rates
   - Collect qualitative feedback on response quality

### Phase 3: Full Migration (Week 5-6)

1. **Enable for All User Types**:
   - Migrate citizen-mode prompts (already enhanced for accessibility)
   - Ensure educational disclaimers remain prominent

2. **Deprecate Old Prompts**:
   - Archive old `prompts.py` as `prompts_legacy.py`
   - Rename `prompts_enhanced.py` → `prompts.py`
   - Update all imports

3. **Documentation**:
   - Update API documentation to reflect enhanced capabilities
   - Create examples showcasing new analysis depth
   - Update marketing materials to highlight elite-level analysis

### Phase 4: Optimization (Ongoing)

1. **Token Budget Optimization**:
   - Analyze actual token usage vs. limits
   - Optimize `max_tokens` settings per complexity level
   - Implement dynamic token allocation

2. **Prompt Refinement**:
   - Collect examples of suboptimal outputs
   - Iteratively refine prompt language
   - A/B test prompt variations

3. **Quality Metrics Tracking**:
   - Maintain dashboard of key quality metrics
   - Set alerts for quality degradation
   - Regular professional review of sample outputs

---

## Quality Metrics

### Quantitative Metrics

1. **Citation Density**: 
   - Target: ≥85% of substantive legal statements cited
   - Measure: `(statements_with_citations / total_legal_statements) * 100`

2. **Citation Accuracy**:
   - Target: 100% of citations verifiable in source documents
   - Measure: Manual verification of sample

3. **Analysis Depth Score**:
   - Criteria: Presence of Issue, Rule, Application, Counterarguments, Practical Implications, Conclusion
   - Target: ≥90% of required elements present

4. **Response Comprehensiveness**:
   - Target: All aspects of query addressed
   - Measure: Professional reviewer assessment (1-5 scale)

5. **Confidence Calibration**:
   - Criteria: Legal position confidence clearly signaled
   - Target: 100% of responses include confidence statement

### Qualitative Metrics

1. **Sophistication Level**:
   - Scale: Basic → Competent → Sophisticated → Elite
   - Assessment: Legal practitioner blind review
   - Target: ≥80% rated "Sophisticated" or "Elite"

2. **Persuasiveness**:
   - Scale: Weak → Adequate → Persuasive → Highly Persuasive
   - Assessment: Would this analysis persuade a judge?
   - Target: ≥75% rated "Persuasive" or "Highly Persuasive"

3. **Practical Utility**:
   - Scale: Not useful → Somewhat useful → Useful → Highly useful
   - Assessment: Can a practitioner use this analysis in practice?
   - Target: ≥85% rated "Useful" or "Highly useful"

4. **Writing Quality**:
   - Criteria: Clarity, precision, authority, readability
   - Assessment: Professional editor review
   - Target: Law review submission quality

---

## Testing Framework

### Unit Tests (Prompt Quality)

```python
# tests/api/composer/test_enhanced_prompts.py

def test_professional_synthesis_includes_all_sections():
    """Test that professional synthesis has required analytical sections."""
    response = invoke_synthesis_prompt(
        query="Can employer terminate without hearing?",
        user_type="professional",
        complexity="complex"
    )
    
    required_sections = [
        "ISSUE",
        "LEGAL FRAMEWORK",
        "AUTHORITY ANALYSIS",
        "APPLICATION",
        "ADVERSARIAL ANALYSIS",
        "PRACTICAL IMPLICATIONS",
        "CONCLUSION"
    ]
    
    for section in required_sections:
        assert section in response, f"Missing required section: {section}"

def test_citation_density_meets_threshold():
    """Test that citation density meets 85% threshold."""
    response = invoke_synthesis_prompt(
        query="What are employee rights on termination?",
        user_type="professional"
    )
    
    citation_density = calculate_citation_density(response)
    assert citation_density >= 0.85, f"Citation density {citation_density} below threshold"

def test_confidence_calibration_present():
    """Test that legal position confidence is explicitly stated."""
    response = invoke_synthesis_prompt(
        query="Can government restrict assembly?",
        user_type="professional"
    )
    
    confidence_markers = [
        "HIGH CONFIDENCE",
        "MODERATE CONFIDENCE",
        "LOW CONFIDENCE",
        "Settled Law",
        "Arguable Position",
        "Uncertain"
    ]
    
    assert any(marker in response for marker in confidence_markers), \
        "No confidence calibration found in response"
```

### Integration Tests (Full Pipeline)

```python
# tests/api/test_end_to_end_quality.py

async def test_complex_query_produces_elite_analysis():
    """Test that complex query produces elite-level analysis."""
    
    query = "Under what circumstances can constitutional rights be limited?"
    
    result = await orchestrator.run_query(AgentState(
        user_id="test_professional",
        session_id="test_session",
        raw_query=query,
        user_type="professional",
        complexity="complex"
    ))
    
    response = result.final_answer
    
    # Quantitative checks
    assert len(response.split()) >= 800, "Response too short for complex analysis"
    assert response.count("(Source:") >= 5, "Insufficient citations"
    
    # Structural checks
    assert "ADVERSARIAL ANALYSIS" in response, "Missing adversarial analysis"
    assert "PRACTICAL IMPLICATIONS" in response, "Missing practical implications"
    
    # Quality checks
    analysis_depth_score = assess_analysis_depth(response)
    assert analysis_depth_score >= 0.9, f"Analysis depth score {analysis_depth_score} too low"
```

### Golden Dataset Evaluation

```python
# tests/evaluation/test_golden_dataset.py

GOLDEN_QUERIES = [
    {
        "query": "Can employer dismiss without hearing?",
        "expected_authorities": ["Section 12 Labour Act", "Nyamande v Cold Comfort"],
        "expected_conclusion": "procedurally unfair",
        "min_words": 600,
        "complexity": "moderate"
    },
    # ... more golden examples
]

@pytest.mark.parametrize("golden_example", GOLDEN_QUERIES)
async def test_golden_query_quality(golden_example):
    """Test response quality against golden dataset."""
    
    result = await orchestrator.run_query(AgentState(
        user_id="test",
        session_id="test",
        raw_query=golden_example["query"],
        complexity=golden_example["complexity"]
    ))
    
    response = result.final_answer
    
    # Check expected authorities cited
    for authority in golden_example["expected_authorities"]:
        assert authority in response, f"Missing expected authority: {authority}"
    
    # Check expected conclusion reached
    assert golden_example["expected_conclusion"] in response.lower(), \
        f"Expected conclusion not found: {golden_example['expected_conclusion']}"
    
    # Check minimum length
    word_count = len(response.split())
    assert word_count >= golden_example["min_words"], \
        f"Response too short: {word_count} < {golden_example['min_words']}"
```

### Professional Review Protocol

1. **Sample Selection**:
   - Randomly select 20 responses per week
   - Stratify by complexity (simple, moderate, complex, expert)
   - Include edge cases and error conditions

2. **Review Criteria**:
   - Legal accuracy (most critical)
   - Citation correctness
   - Analytical sophistication
   - Practical utility
   - Writing quality

3. **Review Scale**:
   ```
   Overall Quality: 1 (Poor) - 2 (Adequate) - 3 (Good) - 4 (Excellent) - 5 (Elite)
   
   Would you be comfortable submitting this analysis to:
   - [ ] A junior associate (basic threshold)
   - [ ] A senior associate (competent threshold)
   - [ ] A partner (sophisticated threshold)
   - [ ] A court (elite threshold)
   ```

4. **Feedback Loop**:
   - Collect specific examples of excellent and poor outputs
   - Use excellent outputs as few-shot examples in prompts
   - Refine prompts to address systematic deficiencies

---

## Cost Considerations

### Token Usage Analysis

**Current System** (Original Prompts):
- Average response: ~400 tokens
- Max tokens setting: 300-1500
- Cost per query: ~$0.002-0.010

**Enhanced System** (Elite Prompts):
- Average response: ~1200 tokens
- Max tokens setting: 800-8000  
- Cost per query: ~$0.006-0.050

**Cost Increase**: ~3-5x for professional/complex queries

### Cost Mitigation Strategies

1. **Tiered Service**:
   - Basic tier: Current prompts (lower cost)
   - Premium tier: Enhanced prompts (higher quality, higher cost)
   - Professional tier: Unlimited enhanced analysis

2. **Complexity-Based Allocation**:
   - Simple queries: Use efficient prompts (~800 tokens)
   - Complex queries: Full elite analysis (~5000 tokens)
   - Dynamic allocation based on query classification

3. **Caching**:
   - Cache common legal framework explanations
   - Reuse authority analysis for frequently cited sources
   - Store synthesized legal positions for common queries

4. **Smart Truncation**:
   - For citizen users, provide shorter but still accurate responses
   - For professional users on moderate complexity, provide medium depth
   - Reserve maximum depth for explicitly complex queries

---

## Success Criteria

### Must-Have (Launch Blockers)

- [ ] **Legal Accuracy**: 100% of legal statements grounded in sources
- [ ] **Citation Accuracy**: 100% of citations verifiable
- [ ] **No Hallucinations**: Zero fabricated authorities or provisions
- [ ] **Appropriate Disclaimers**: All advice-seeking queries have disclaimers

### Should-Have (Quality Targets)

- [ ] **Citation Density**: ≥85% of legal statements cited
- [ ] **Analysis Depth**: ≥90% of responses include all required sections
- [ ] **Professional Rating**: ≥80% rated "Sophisticated" or "Elite" by lawyers
- [ ] **Confidence Calibration**: 100% of responses signal certainty level

### Nice-to-Have (Aspirational Goals)

- [ ] **Law Review Quality**: 50% of expert-level responses rated at law review standard
- [ ] **Judicial Citation**: Gweta analysis cited in court proceedings (ultimate validation)
- [ ] **Academic Recognition**: Legal scholars reference Gweta's analytical framework
- [ ] **Bar Association Endorsement**: Recognized by Law Society as legitimate research tool

---

## Conclusion

The enhanced prompting system transforms Gweta from a competent legal information system into an AI assistant capable of producing elite-level legal analysis. The improvements span:

1. **Analytical Depth**: Multi-layered reasoning with adversarial thinking
2. **Scholarly Rigor**: Sophisticated legal writing and precise terminology
3. **Authority Mastery**: Deep understanding of hierarchy and precedent
4. **Practical Integration**: Policy awareness and strategic guidance
5. **Intellectual Honesty**: Clear confidence calibration and gap acknowledgment

The migration strategy balances quality improvement with cost management, starting with professional users and complex queries where the value proposition is clearest.

Success will be measured by both quantitative metrics (citation density, accuracy) and qualitative assessment by legal professionals. The ultimate validation will be when Gweta's analysis is sufficiently sophisticated that legal practitioners rely on it for preliminary research and strategic analysis—not just basic legal information.

This represents a paradigm shift from "legal search engine with AI summarization" to "AI legal researcher and analyst."
