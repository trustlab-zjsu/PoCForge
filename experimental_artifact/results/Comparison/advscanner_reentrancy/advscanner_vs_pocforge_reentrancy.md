# Advscanner vs PoCForge (Reentrancy)

- Total reentrancy findings: 13
- PoCForge success: 10/13 (76.9%)
- Source fetch success: 13/13 (100.0%)
- Slither reentrancy detected: 13/13 (100.0%)
- Advscanner PoC generated: 13/13 (100.0%)
- Advscanner Compile Pass (CSR-like): 4/13 (30.8%)
- Advscanner EVM Pass (ERR-like): 2/13 (15.4%)
- Advscanner Oracle Pass (VPR-like): 1/13 (7.7%)

## Notes
- `advscanner_poc_generated` is only code generation success.
- Success quality should be judged by compile/EVM/oracle metrics.