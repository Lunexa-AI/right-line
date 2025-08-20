"""Hardcoded legal responses for RightLine MVP.

This module provides hardcoded responses for common legal queries.
Used in Phase 1 MVP to validate concept before implementing real search.
"""

from __future__ import annotations

import re
import time
from typing import Any

from api.models import Citation, QueryResponse, SectionRef

# Hardcoded Q&A pairs from Labour Act and common legal questions
HARDCODED_RESPONSES: dict[str, dict[str, Any]] = {
    "minimum_wage": {
        "keywords": ["minimum wage", "wage", "salary", "pay", "earnings"],
        "summary": "The minimum wage in Zimbabwe is set by statutory instrument.\nIt varies by sector and is reviewed periodically.\nEmployers must pay at least the prescribed minimum wage.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12A",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 15,
                "sha": "labour_act_12a_2024",
            },
            {
                "title": "Statutory Instrument 118 of 2024",
                "url": "https://gazette.gov.zw/si-118-2024",
                "page": 4,
                "sha": "si_118_2024",
            },
        ],
        "confidence": 0.9,
        "related_sections": ["12B", "13A", "99"],
    },
    
    "working_hours": {
        "keywords": ["working hours", "work time", "overtime", "hours", "shift"],
        "summary": "Normal working hours are 8 hours per day or 40 hours per week.\nOvertime must be paid at 1.5 times the normal rate.\nEmployees cannot work more than 60 hours per week including overtime.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "14",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 18,
                "sha": "labour_act_14_2024",
            },
        ],
        "confidence": 0.95,
        "related_sections": ["15", "16", "17"],
    },
    
    "leave_entitlement": {
        "keywords": ["leave", "vacation", "holiday", "annual leave", "sick leave"],
        "summary": "Employees are entitled to 30 days annual leave per year.\nSick leave is available with medical certificate.\nMaternity leave is 98 days for female employees.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "18",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 22,
                "sha": "labour_act_18_2024",
            },
        ],
        "confidence": 0.88,
        "related_sections": ["19", "20", "21"],
    },
    
    "termination": {
        "keywords": ["termination", "dismissal", "firing", "retrenchment", "notice"],
        "summary": "Employment can be terminated with proper notice period.\nNotice period depends on length of service.\nUnfair dismissal claims can be made to labour court.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 14,
                "sha": "labour_act_12_2024",
            },
        ],
        "confidence": 0.85,
        "related_sections": ["12B", "12C", "99"],
    },
    
    "contract_employment": {
        "keywords": ["contract", "employment contract", "agreement", "terms"],
        "summary": "Employment contracts must be in writing within 30 days.\nContracts must specify wages, hours, and conditions.\nBoth parties must agree to any changes in writing.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "5",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 8,
                "sha": "labour_act_5_2024",
            },
        ],
        "confidence": 0.92,
        "related_sections": ["6", "7", "8"],
    },
    
    "workplace_safety": {
        "keywords": ["safety", "health", "workplace safety", "occupational health", "accident"],
        "summary": "Employers must provide a safe working environment.\nSafety equipment must be provided free of charge.\nAccidents must be reported to relevant authorities.",
        "section_ref": {
            "act": "Occupational Safety and Health Act",
            "chapter": "15:05",
            "section": "6",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Occupational Safety and Health Act [Chapter 15:05]",
                "url": "https://veritas.org.zw/osh-act-chapter-15-05",
                "page": 10,
                "sha": "osh_act_6_2024",
            },
        ],
        "confidence": 0.87,
        "related_sections": ["7", "8", "15"],
    },
    
    "discrimination": {
        "keywords": ["discrimination", "harassment", "equal treatment", "gender", "race"],
        "summary": "Discrimination based on race, gender, religion is prohibited.\nEmployers must ensure equal treatment of all employees.\nComplaints can be made to labour relations officer.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "4",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 6,
                "sha": "labour_act_4_2024",
            },
        ],
        "confidence": 0.90,
        "related_sections": ["4A", "4B", "99"],
    },
    
    "trade_unions": {
        "keywords": ["trade union", "union", "collective bargaining", "worker rights"],
        "summary": "Workers have the right to join trade unions.\nUnions can engage in collective bargaining.\nEmployers cannot discriminate against union members.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "25",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 30,
                "sha": "labour_act_25_2024",
            },
        ],
        "confidence": 0.86,
        "related_sections": ["26", "27", "28"],
    },
    
    # Additional legal topics for comprehensive coverage (Task 1.1.2)
    
    "probation_period": {
        "keywords": ["probation", "probationary period", "trial period", "new employee"],
        "summary": "Probation period cannot exceed 3 months.\nDuring probation, either party can terminate with 1 day notice.\nProbation terms must be in writing.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12D",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 16,
                "sha": "labour_act_12d_2024",
            },
        ],
        "confidence": 0.91,
        "related_sections": ["12", "12A", "12B"],
    },
    
    "maternity_leave": {
        "keywords": ["maternity", "maternity leave", "pregnancy", "pregnant", "childbirth"],
        "summary": "Female employees entitled to 98 days maternity leave.\nAt least 45 days must be taken after childbirth.\nMaternity leave is on full pay for first birth.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "18",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 23,
                "sha": "labour_act_18_2024",
            },
        ],
        "confidence": 0.94,
        "related_sections": ["19", "20"],
    },
    
    "sick_leave": {
        "keywords": ["sick leave", "illness", "medical", "sick", "doctor certificate"],
        "summary": "Employees get 90 days sick leave per year on full pay.\nMedical certificate required after 2 consecutive days.\nSick leave cannot be carried forward.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "19",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 24,
                "sha": "labour_act_19_2024",
            },
        ],
        "confidence": 0.93,
        "related_sections": ["18", "20", "21"],
    },
    
    "public_holidays": {
        "keywords": ["public holiday", "holiday", "national holiday", "holiday pay"],
        "summary": "Employees entitled to all gazetted public holidays.\nWork on public holidays paid at double normal rate.\nEmployer cannot deduct pay for public holidays.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "17",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 21,
                "sha": "labour_act_17_2024",
            },
        ],
        "confidence": 0.89,
        "related_sections": ["14", "15", "16"],
    },
    
    "resignation": {
        "keywords": ["resignation", "resign", "quit", "leaving job", "notice period resignation"],
        "summary": "Employee must give notice as per contract or statutory minimum.\nNotice period same as for termination by employer.\nEmployee can leave immediately if pays lieu of notice.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12C",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 15,
                "sha": "labour_act_12c_2024",
            },
        ],
        "confidence": 0.88,
        "related_sections": ["12", "12A", "12B"],
    },
    
    "severance_pay": {
        "keywords": ["severance", "severance pay", "retrenchment package", "termination benefits"],
        "summary": "Minimum severance is 1 month salary per 2 years service.\nPaid on retrenchment or abolition of post.\nNot payable for misconduct dismissal.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12C",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 16,
                "sha": "labour_act_12c_2024",
            },
            {
                "title": "Statutory Instrument 137 of 2023",
                "url": "https://gazette.gov.zw/si-137-2023",
                "page": 2,
                "sha": "si_137_2023",
            },
        ],
        "confidence": 0.90,
        "related_sections": ["12", "12B", "99"],
    },
    
    "disciplinary_procedures": {
        "keywords": ["disciplinary", "discipline", "misconduct", "warning", "hearing"],
        "summary": "Employee must be given chance to be heard before dismissal.\nSerious misconduct may warrant summary dismissal.\nProgressive discipline: warning, final warning, dismissal.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12B",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 14,
                "sha": "labour_act_12b_2024",
            },
            {
                "title": "Code of Conduct SI 15/2006",
                "url": "https://gazette.gov.zw/si-15-2006",
                "page": 5,
                "sha": "si_15_2006",
            },
        ],
        "confidence": 0.92,
        "related_sections": ["12", "12A", "99"],
    },
    
    "unfair_dismissal": {
        "keywords": ["unfair dismissal", "wrongful termination", "illegal firing", "labour court"],
        "summary": "Dismissed employee can appeal to labour officer within 3 months.\nIf unfair, reinstatement or damages may be ordered.\nBurden of proof on employer to justify dismissal.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "89",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 95,
                "sha": "labour_act_89_2024",
            },
        ],
        "confidence": 0.91,
        "related_sections": ["90", "91", "93"],
    },
    
    "gratuity": {
        "keywords": ["gratuity", "end of service", "long service", "retirement benefit"],
        "summary": "Gratuity paid after continuous service as per contract.\nUsually calculated as percentage of final salary.\nTax treatment depends on years of service.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "14A",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 19,
                "sha": "labour_act_14a_2024",
            },
        ],
        "confidence": 0.85,
        "related_sections": ["12C", "99"],
    },
    
    "child_labour": {
        "keywords": ["child labour", "child labor", "minimum age", "young worker", "apprentice"],
        "summary": "Minimum employment age is 16 years.\nChildren 16-18 cannot do hazardous work.\nApprentices can start at 14 with guardian consent.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "11",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 13,
                "sha": "labour_act_11_2024",
            },
            {
                "title": "Children's Act [Chapter 5:06]",
                "url": "https://veritas.org.zw/childrens-act",
                "page": 45,
                "sha": "childrens_act_2024",
            },
        ],
        "confidence": 0.93,
        "related_sections": ["11A", "11B"],
    },
    
    "pension_contributions": {
        "keywords": ["pension", "NSSA", "social security", "retirement", "contributions"],
        "summary": "NSSA contributions mandatory for all employees.\nEmployer and employee each contribute 4.5% of salary.\nContributions capped at maximum insurable earnings.",
        "section_ref": {
            "act": "NSSA Act",
            "chapter": "17:04",
            "section": "14",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "National Social Security Authority Act [Chapter 17:04]",
                "url": "https://veritas.org.zw/nssa-act",
                "page": 18,
                "sha": "nssa_act_14_2024",
            },
        ],
        "confidence": 0.92,
        "related_sections": ["15", "16", "20"],
    },
    
    "medical_aid": {
        "keywords": ["medical aid", "health insurance", "medical benefits", "healthcare"],
        "summary": "No legal requirement to provide medical aid.\nIf provided, must be clearly stated in contract.\nEmployer contribution to medical aid is taxable benefit.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "6A",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 9,
                "sha": "labour_act_6a_2024",
            },
        ],
        "confidence": 0.84,
        "related_sections": ["6", "7"],
    },
    
    "workplace_accidents": {
        "keywords": ["accident", "injury", "workplace accident", "compensation", "WCIF"],
        "summary": "Report workplace accidents within 14 days.\nWorker's compensation covers medical costs and lost wages.\nEmployer liable if negligent in providing safety.",
        "section_ref": {
            "act": "WCIF Act",
            "chapter": "19:05",
            "section": "68",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Workers Compensation Insurance Fund Act",
                "url": "https://veritas.org.zw/wcif-act",
                "page": 72,
                "sha": "wcif_act_68_2024",
            },
        ],
        "confidence": 0.89,
        "related_sections": ["69", "70", "71"],
    },
    
    "sexual_harassment": {
        "keywords": ["sexual harassment", "harassment", "inappropriate behavior", "workplace harassment"],
        "summary": "Sexual harassment is grounds for dismissal.\nEmployer must have anti-harassment policy.\nVictim can report to labour officer or police.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "8",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 11,
                "sha": "labour_act_8_2024",
            },
            {
                "title": "SI 12 of 2021 - Workplace Sexual Harassment",
                "url": "https://gazette.gov.zw/si-12-2021",
                "page": 3,
                "sha": "si_12_2021",
            },
        ],
        "confidence": 0.95,
        "related_sections": ["4", "8A", "99"],
    },
    
    "fixed_term_contracts": {
        "keywords": ["fixed term", "contract worker", "temporary", "casual labour"],
        "summary": "Fixed term contracts automatically end on expiry date.\nRenewal more than once creates permanent employment expectation.\nSame benefits as permanent staff during contract period.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 14,
                "sha": "labour_act_12_2024",
            },
        ],
        "confidence": 0.87,
        "related_sections": ["12A", "12B"],
    },
    
    "deductions": {
        "keywords": ["deductions", "salary deductions", "wage deductions", "unauthorized deduction"],
        "summary": "Only statutory deductions allowed without consent.\nOther deductions need written employee agreement.\nTotal deductions cannot exceed one-third of wages.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12A",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 15,
                "sha": "labour_act_12a_2024",
            },
        ],
        "confidence": 0.90,
        "related_sections": ["13", "14"],
    },
    
    "rest_periods": {
        "keywords": ["rest", "break", "lunch break", "tea break", "rest period"],
        "summary": "30 minute meal break after 5 continuous hours work.\nWeekly rest period of at least 24 continuous hours.\nRest periods not counted as working time.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "15",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 20,
                "sha": "labour_act_15_2024",
            },
        ],
        "confidence": 0.88,
        "related_sections": ["14", "16"],
    },
    
    "transport_allowance": {
        "keywords": ["transport", "transport allowance", "travel allowance", "commute"],
        "summary": "Transport allowance not mandatory unless in contract.\nIf provided, forms part of conditions of service.\nEmployer transport must meet safety standards.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "6",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 9,
                "sha": "labour_act_6_2024",
            },
        ],
        "confidence": 0.82,
        "related_sections": ["6A", "7"],
    },
    
    "housing_allowance": {
        "keywords": ["housing", "accommodation", "housing allowance", "rent allowance"],
        "summary": "Housing allowance not mandatory by law.\nIf provided, taxable as benefit in kind.\nEmployer accommodation must meet health standards.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "6",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 9,
                "sha": "labour_act_6_2024",
            },
        ],
        "confidence": 0.81,
        "related_sections": ["6A", "7"],
    },
    
    "overtime_pay": {
        "keywords": ["overtime", "extra hours", "overtime pay", "overtime rate", "sunday work", "holiday work", "sunday payment", "working extra"],
        "summary_3_lines": "Overtime work must be paid at 1.5x normal rate for regular overtime.\nSunday and public holiday work paid at 2x normal rate.\nMaximum 24 hours overtime per week allowed.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "14A",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 14A", "url": "https://law.co.zw/labour-act-14a", "page": 15},
            {"title": "SI 56/2024 Overtime Regulations", "url": "https://law.co.zw/si-56-2024"}
        ],
        "confidence": 0.95,
        "related_sections": ["working_hours", "public_holidays", "rest_periods"]
    },
    
    "notice_period": {
        "keywords": ["notice", "notice period", "resignation notice", "termination notice", "notice pay"],
        "summary_3_lines": "Notice period depends on length of service and contract terms.\nMinimum 1 month for permanent employees, 2 weeks for probation.\nPayment in lieu of notice is permissible.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 12", "url": "https://law.co.zw/labour-act-12", "page": 8},
            {"title": "Employment Termination Guidelines", "url": "https://law.co.zw/termination-guide"}
        ],
        "confidence": 0.92,
        "related_sections": ["termination", "resignation", "severance_pay"]
    },
    
    "paternity_leave": {
        "keywords": ["paternity", "father leave", "paternal leave", "dad leave", "new father"],
        "summary_3_lines": "Fathers entitled to 2 weeks paid paternity leave.\nMust be taken within 30 days of child's birth.\nRequires birth certificate or medical proof.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "18A",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 18A", "url": "https://law.co.zw/labour-act-18a", "page": 22},
            {"title": "Parental Leave Regulations", "url": "https://law.co.zw/parental-leave"}
        ],
        "confidence": 0.94,
        "related_sections": ["maternity_leave", "leave_entitlement"]
    },
    
    "retrenchment": {
        "keywords": ["retrenchment", "layoff", "redundancy", "downsizing", "job cuts", "retrenchment process"],
        "summary_3_lines": "Retrenchment requires board approval and worker consultation.\nMinimum package: 1 month salary per year of service.\nNotice period of at least 3 months required.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12C",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 12C", "url": "https://law.co.zw/labour-act-12c", "page": 10},
            {"title": "Retrenchment Guidelines 2024", "url": "https://law.co.zw/retrenchment-2024"}
        ],
        "confidence": 0.96,
        "related_sections": ["severance_pay", "termination", "notice_period"]
    },
    
    "collective_bargaining": {
        "keywords": ["collective bargaining", "union negotiation", "workers agreement", "collective agreement"],
        "summary_3_lines": "Workers have right to collective bargaining through unions.\nEmployers must recognize registered trade unions.\nCollective agreements are legally binding.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "74",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 74", "url": "https://law.co.zw/labour-act-74", "page": 95},
            {"title": "Collective Bargaining Procedures", "url": "https://law.co.zw/collective-bargaining"}
        ],
        "confidence": 0.91,
        "related_sections": ["trade_unions", "grievance_procedures"]
    },
    
    "casual_workers": {
        "keywords": ["casual", "casual worker", "temporary worker", "part time", "casual employment"],
        "summary_3_lines": "Casual workers employed for less than 6 weeks continuously.\nEntitled to pro-rata leave and proportional benefits.\nMust be registered and paid at least minimum wage.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "7",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 7", "url": "https://law.co.zw/labour-act-7", "page": 5},
            {"title": "Casual Employment Regulations", "url": "https://law.co.zw/casual-employment"}
        ],
        "confidence": 0.89,
        "related_sections": ["contract_employment", "minimum_wage"]
    },
    
    "retirement_age": {
        "keywords": ["retirement", "retirement age", "pension age", "retire", "mandatory retirement"],
        "summary_3_lines": "Normal retirement age is 60-65 years depending on sector.\nEarly retirement possible with reduced benefits.\nCompulsory retirement cannot be enforced below 60.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "12B",
            "version": "2024"
        },
        "citations": [
            {"title": "Labour Act Section 12B", "url": "https://law.co.zw/labour-act-12b", "page": 9},
            {"title": "Retirement Policy Framework", "url": "https://law.co.zw/retirement-policy"}
        ],
        "confidence": 0.90,
        "related_sections": ["pension_contributions", "gratuity"]
    },
    
    "grievance_procedures": {
        "keywords": ["grievance", "complaint", "dispute", "workplace dispute"],
        "summary": "Employee must first raise grievance with immediate supervisor.\nIf unresolved, escalate to management then labour officer.\nGrievance procedures must be in employment code.",
        "section_ref": {
            "act": "Labour Act",
            "chapter": "28:01",
            "section": "101",
            "version": "2024-01-01",
        },
        "citations": [
            {
                "title": "Labour Act [Chapter 28:01]",
                "url": "https://veritas.org.zw/labour-act-chapter-28-01",
                "page": 110,
                "sha": "labour_act_101_2024",
            },
        ],
        "confidence": 0.87,
        "related_sections": ["102", "103", "104"],
    },
}

# Default fallback response for unmatched queries
DEFAULT_RESPONSE = {
    "summary": "I couldn't find specific information for your query.\nPlease try rephrasing your question or be more specific.\nFor urgent legal matters, consult a qualified lawyer.",
    "section_ref": {
        "act": "General Information",
        "chapter": "N/A",
        "section": "FAQ",
        "version": None,
    },
    "citations": [
        {
            "title": "RightLine Legal Information Service",
            "url": "https://rightline.zw/help",
            "page": None,
            "sha": None,
        },
    ],
    "confidence": 0.1,
    "related_sections": [],
}


def normalize_query(text: str) -> str:
    """Normalize query text for keyword matching.
    
    Args:
        text: Raw query text
        
    Returns:
        Normalized text in lowercase with extra whitespace removed
    """
    # Convert to lowercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    
    # Remove common stop words that don't affect legal meaning
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'what', 'when', 'where', 'why', 'how'}
    
    words = normalized.split()
    filtered_words = [word for word in words if word not in stop_words]
    
    return ' '.join(filtered_words)


def calculate_keyword_match_score(query: str, keywords: list[str]) -> float:
    """Calculate keyword match score between query and response keywords.
    
    Args:
        query: Normalized query text
        keywords: List of keywords for a response
        
    Returns:
        Match score between 0.0 and 1.0
    """
    query_words = set(query.split())
    total_score = 0.0
    
    for keyword in keywords:
        keyword_words = set(keyword.lower().split())
        
        # Exact phrase match gets highest score
        if keyword.lower() in query:
            total_score += 1.0
        # Partial word overlap gets proportional score
        else:
            overlap = len(query_words.intersection(keyword_words))
            if overlap > 0:
                total_score += overlap / len(keyword_words)
    
    # Normalize by number of keywords
    return min(total_score / len(keywords), 1.0) if keywords else 0.0


def get_hardcoded_response(query_text: str, lang_hint: str | None = None) -> QueryResponse:
    """Get hardcoded response for a legal query.
    
    This function matches the query against predefined legal Q&A pairs
    and returns the most relevant response with proper citations.
    
    Args:
        query_text: The legal question or query
        lang_hint: Optional language hint (currently not used in MVP)
        
    Returns:
        QueryResponse with legal information and citations
        
    Raises:
        ValueError: If query_text is empty or invalid
    """
    if not query_text or not query_text.strip():
        raise ValueError("Query text cannot be empty")
    
    # Normalize the query for matching
    normalized_query = normalize_query(query_text)
    
    # Find the best matching response
    best_match = None
    best_score = 0.0
    
    for response_key, response_data in HARDCODED_RESPONSES.items():
        score = calculate_keyword_match_score(normalized_query, response_data["keywords"])
        
        if score > best_score:
            best_score = score
            best_match = response_data
    
    # Use best match if score is above threshold, otherwise use default
    if best_match and best_score >= 0.3:
        response_data = best_match
        # Adjust confidence based on match quality
        confidence = response_data["confidence"] * best_score
    else:
        response_data = DEFAULT_RESPONSE
        confidence = DEFAULT_RESPONSE["confidence"]
    
    # Create response objects
    section_ref = SectionRef(**response_data["section_ref"])
    citations = [Citation(**citation) for citation in response_data["citations"]]
    
    # Convert old format to new format
    summary = response_data.get("summary_3_lines") or response_data.get("summary", "")
    
    # Split summary into tldr and key points
    lines = summary.split('\n')
    tldr = lines[0] if lines else "Legal information available."
    key_points = lines[1:] if len(lines) > 1 else ["Consult legal counsel for specific advice."]
    
    # Ensure we have at least 3 key points
    while len(key_points) < 3:
        key_points.append("Additional information available in referenced legal documents.")
    
    # Generate suggestions based on the topic
    suggestions = [
        "What are the penalties for violations?",
        "How do I file a complaint?",
        "What are my rights as an employee?"
    ]
    
    return QueryResponse(
        tldr=tldr,
        key_points=key_points[:5],  # Limit to 5
        citations=citations,
        suggestions=suggestions,
        confidence=confidence,
        source="hardcoded",
        request_id=f"req_{int(time.time() * 1000000)}"
    )


def get_available_topics() -> list[str]:
    """Get list of available legal topics in hardcoded responses.
    
    Returns:
        List of topic keys that have hardcoded responses
    """
    return list(HARDCODED_RESPONSES.keys())


def get_response_by_topic(topic: str) -> dict[str, Any] | None:
    """Get hardcoded response data by topic key.
    
    Args:
        topic: Topic key from HARDCODED_RESPONSES
        
    Returns:
        Response data dictionary or None if topic not found
    """
    return HARDCODED_RESPONSES.get(topic)
