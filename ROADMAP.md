# EcoPolicy-AI Roadmap

## Phase 1: Foundation [DONE]

- [x] Policy monitoring tool (fetcher + parsers + database)
- [x] 37 national data sources (State Council API x 32 + verified HTML x 5)
- [x] 31 provincial region configurations (all mainland provinces/municipalities/autonomous regions)
- [x] Industry classification system (5 categories, 43 sub-industries)
- [x] Agent orchestration system (scanner + matcher + report + notifier)
- [x] Enterprise profile template (10 dimensions + business model for asset-light)
- [x] 7 industry-specific analysis frameworks (40+ keywords each)
- [x] Standard analysis workflow (6 steps)
- [x] Output standards (5-point scoring, P0/P1/P2 priority, formatting)
- [x] 3 demo case studies
- [x] CLI English localization (all terminal output in English)

## Phase 2: Validation & Optimization [DONE]

- [x] Multi-industry case validation (5 industries: manufacturing, digital economy, new energy, biopharma, new materials)
- [x] GitHub repository setup and initial push
- [x] Expanded policy sources (+12: NMPA/NHSA/NDA/PBOC/CSRC/CNIPA/SASAC/MOHRSS/SAMR/MOE/MCT/MCA)
- [x] Deep industry analysis (7 dimension-specific keyword systems, 40+ keywords each)
- [x] Asset-light industry adaptation (business_model module, digital asset dimensions)
- [x] Feedback mechanism (accept/reject/outcome tracking + accuracy/usefulness scoring)
- [x] Scheduled task integration (Python scheduler + Windows Task Scheduler + Linux cron)
- [x] Security review automation (`security_review.py` for pre-push checks)
- [ ] Enterprise multi-profile isolation test (2nd enterprise)

## Phase 3: Agent Enhancement [PLANNED]

- [ ] Multi-turn conversation support for deep analysis
- [ ] Application draft generation (feasibility report outlines)
- [ ] Batch matching (one enterprise against multiple policies, ranked by priority)
- [ ] Historical policy trend analysis and change tracking
- [ ] Cross-region policy comparison

## Phase 4: Interface & API [PLANNED]

- [ ] Web dashboard (Flask/FastAPI)
- [ ] REST API for external integration
- [ ] Email / WeChat notification integration
- [ ] PDF report generation (CJK-compatible)

## Phase 5: Community & Scale [PLANNED]

- [ ] More industry analysis templates (healthcare, logistics, finance)
- [ ] More provincial data sources (community-contributed)
- [ ] Multi-language support (English policy summary)
- [ ] Plugin architecture for custom analyzers

---

## Contributing

See [README.md](README.md) for setup instructions.

## License

MIT
