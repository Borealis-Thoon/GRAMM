from pathlib import Path
import json, statistics, math, hashlib, argparse
ROOT=Path(__file__).resolve().parents[2]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def exact_sign_p(values):
    signs=[v>0 for v in values if v!=0]
    n=len(signs)
    k=min(sum(signs),n-sum(signs))
    return min(1.0,2*sum(math.comb(n,j) for j in range(k+1))/2**n) if n else 1.0

def review(records_path, summary_path):
    records=json.loads(records_path.read_text())
    summary=json.loads(summary_path.read_text())
    measured=[r for r in records if r['measured']]
    lookup={(r['case'],r['variant'],r['rep']):r for r in measured}
    rows=[]
    for row in summary['rows']:
        case,variant=row['case'],row['variant']
        baseline=sorted([r for r in measured if r['case']==case and r['variant']=='baseline'],key=lambda r:r['rep'])
        pairs=[(b,lookup[(case,variant,b['rep'])]) for b in baseline]
        percentages=[100*(1-p['lifetime_seconds']/b['lifetime_seconds']) for b,p in pairs]
        absolute=[b['lifetime_seconds']-p['lifetime_seconds'] for b,p in pairs]
        assert len(pairs)==row['pairs']
        assert abs(statistics.median(percentages)-row['paired_time_saved_pct'])<1e-10
        baseline_median=statistics.median(b['lifetime_seconds'] for b,p in pairs)
        baseline_spread=max(b['lifetime_seconds'] for b,p in pairs)-min(b['lifetime_seconds'] for b,p in pairs)
        n=len(pairs)
        rows.append({
            'case':case,'variant':variant,'pairs':n,
            'paired_median_time_saved_percent':statistics.median(percentages),
            'paired_median_time_saved_seconds':statistics.median(absolute),
            'faster_pairs':sum(v>0 for v in percentages),
            'baseline_median_seconds':baseline_median,
            'baseline_observed_range_seconds':baseline_spread,
            'baseline_observed_range_percent_of_median':100*baseline_spread/baseline_median,
            'observed_percent_range':[min(percentages),max(percentages)],
            'reported_percentile_bootstrap_range':[row['low_pct'],row['high_pct']],
            'bootstrap_endpoints_equal_sample_extrema':abs(row['low_pct']-min(percentages))<1e-10 and abs(row['high_pct']-max(percentages))<1e-10,
            'sample_min_max_coverage_for_population_median_under_iid_continuous_assumption':1-2*(.5**n),
            'two_sided_exact_sign_p_unadjusted':exact_sign_p(percentages),
            'sign_p_is_diagnostic_not_submission_threshold':True,
            'raw_summary_reconciled':True,
        })
    candidates={}
    for variant in sorted({r['variant'] for r in rows}):
        vr=[r for r in rows if r['variant']==variant]
        candidates[variant]={
            'preliminary_submission_recommendation':'hold_pending_independent_work_matched_confirmation',
            'confirmed_practical_runtime_benefit':False,
            'pooled_positive_pairs_descriptive_only':sum(r['faster_pairs'] for r in vr),
            'pooled_pairs_descriptive_only':sum(r['pairs'] for r in vr),
            'case_medians_positive':sum(r['paired_median_time_saved_percent']>0 for r in vr),
            'case_medians_nonpositive':sum(r['paired_median_time_saved_percent']<=0 for r in vr),
            'smallest_case_median_percent':min(r['paired_median_time_saved_percent'] for r in vr),
            'largest_case_median_percent':max(r['paired_median_time_saved_percent'] for r in vr),
            'pooling_not_used_for_inference':True,
        }
    candidates['tdma']['structural_benefit']={'files':1,'added_lines':15,'deleted_lines':26,'removed_stack_arrays':2,'stack_bytes_saved_per_kernel_invocation':'16 * (2 * NK - 1)','stack_bytes_saved_at_NK_28':880,'structural_benefit_does_not_establish_runtime_gain':True}
    candidates['tdma']['main_rationale_codes']=['large_case_five_positive_pairs_but_0_350_percent_median','two_single_thread_case_medians_negative','simpler_code_and_less_stack_are_real_but_user_requests_demonstrated_benefit']
    candidates['pressure']['main_rationale_codes']=['benefit_direction_varies_by_case','five_of_six_bootstrap_ranges_cross_zero','positive_three_pair_short_case_insufficient_independent_confirmation']
    candidates['radiation']['main_rationale_codes']=['all_six_bootstrap_ranges_cross_zero','large_case_median_0_025_percent','convective_case_four_of_five_pairs_slower']
    return {
        'status':'preliminary_review_complete','decision_scope':'initial_six_native_cases_only',
        'source_files':{'records':str(records_path),'records_sha256':sha(records_path),'summary':str(summary_path),'summary_sha256':sha(summary_path)},
        'run_counts':{'total':len(records),'measured':len(measured),'warmups_excluded':len(records)-len(measured),'cases':len({r['case'] for r in measured}),'candidate_case_comparisons':len(rows)},
        'measurement_scope':'native_process_lifetime_including_startup_initialization_integration_and_output',
        'design_strengths':['unmodified_native_dispatch','rotating_variant_order','warmup_excluded','all_measured_repeats_retained','three_grid_scales','one_four_eight_configured_threads','neutral_stable_convective_radiation_conditions'],
        'interpretation_controls':['no_cross_case_pooling_for_claims','no_arbitrary_one_percent_cutoff','no_lifetime_claim_as_solver_only_time','no_peak_working_set_noise_claim_as_memory_saving','no_quantized_output_hash_as_full_precision_fidelity','no_selection_of_best_case_as_general_speedup','no_noninferiority_or_equivalence_claim_from_nonsignificance'],
        'remaining_evidence_codes':['independent_fixed_dt_or_confirmed_equal_iteration_work','planned_scalar_candidate_measured_separately','paired_runtime_gain_reproducible_under_representative_load','material_losses_in_tested_conditions_resolved_or_avoided','full_precision_numerical_validation_linked_separately'],
        'small_sample_bootstrap_flag':{'all_reported_intervals_equal_observed_extrema':all(r['bootstrap_endpoints_equal_sample_extrema'] for r in rows),'positive_lower_bound_comparisons':sum(r['reported_percentile_bootstrap_range'][0]>0 for r in rows),'cannot_treat_nominal_95_percent_as_calibrated_coverage_at_n3_n5':True},
        'rows':rows,'candidates':candidates,
        'future_update':{'retain_current_file':True,'write_final_review_after_fixed_dt_and_scalar_results':True,'evaluate_all_observed_outcomes_without_discarding_unfavorable_repeats':True,'if_benefit_remains_unresolved':'do_not_submit_per_user_policy'}
    }
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--records',type=Path,default=ROOT/'qa/native/results.json');p.add_argument('--summary',type=Path,default=ROOT/'qa/native/summary.json');p.add_argument('--out',type=Path,default=Path(__file__).with_name('preliminary_review.json'));a=p.parse_args()
    result=review(a.records,a.summary);a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'counts':result['run_counts'],'candidates':{k:v['preliminary_submission_recommendation'] for k,v in result['candidates'].items()}}))
