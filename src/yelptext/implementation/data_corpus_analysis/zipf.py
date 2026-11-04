"""Provenance guards shared by enhanced corpus notebooks."""
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .heaps import file_sha256, tokenizer_identity, write_json, archive_previous_results


def analyze_zipf(vocabulary_path, tokenizer, output_dir, *, backup_root=None):
    output = Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    path = Path(vocabulary_path).resolve()
    identity = tokenizer_identity(tokenizer)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as connection:
        metadata = {k:json.loads(v) for k,v in connection.execute('SELECT key,value_json FROM metadata')}
        if metadata.get('status') != 'COMPLETED' or metadata.get('tokenizer_fingerprint') != identity['fingerprint']:
            raise ValueError('Vocabulary is incomplete or tokenizer fingerprint differs. Rebuild vocabulary.')
        if metadata.get('min_cf') != 1 or metadata.get('min_df') != 1 or metadata.get('skip_types') != []:
            raise ValueError('Zipf requires unpruned, unfiltered observed terms.')
        terms = pd.read_sql_query('SELECT term,cf,df FROM terms WHERE term_id <> 0 AND cf > 0 ORDER BY cf DESC,term',connection)
    terms = terms[~terms['term'].isin(['!','?','#'])].copy()
    terms['rank'] = np.arange(1,len(terms)+1)
    if len(terms)<2:
        raise ValueError('Too few observed types')
    archive_previous_results(backup_root or output.parent.parent, output)
    terms[['rank','term','cf','df']].to_csv(output/'rank_frequency.csv',index=False)
    terms[['rank','term','cf','df']].head(100).to_csv(output/'top_100.csv',index=False)
    masks = {'all_ranks': np.ones(len(terms),dtype=bool),
             'rank_1_500':terms['rank']<=500,'rank_1_1000':terms['rank']<=1000,
             'rank_1_5000':terms['rank']<=5000,
             'rank_1000_100000':(terms['rank']>=1000)&(terms['rank']<=100000),
             'frequency_at_least_5':terms['cf']>=5}
    fits=[]
    for name,mask in masks.items():
        subset=terms[mask]
        if len(subset)<2:
            continue
        x=np.log(subset['rank'].to_numpy()); y=np.log(subset['cf'].to_numpy())
        slope,intercept=np.polyfit(x,y,1)
        total=float(np.sum((y-y.mean())**2))
        fits.append({'fit':name,'rank_min':int(subset['rank'].min()),'rank_max':int(subset['rank'].max()),
                     'types':len(subset),'slope':float(slope),'zipf_s':float(-slope),'K':float(np.exp(intercept)),
                     'r_squared_log_space':float(1-np.sum((y-intercept-slope*x)**2)/total) if total else None})
    pd.DataFrame(fits).to_csv(output/'fit_comparison.csv',index=False)
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    ax.loglog(terms['rank'],terms['cf'],color='#2463A5',label='Observed (all filtered types)')
    for name,color in [('all_ranks','#8A94A6'),('rank_1_1000','#C37722')]:
        row=next((r for r in fits if r['fit']==name),None)
        if row:
            x=np.geomspace(row['rank_min'],row['rank_max'],200)
            ax.loglog(x,row['K']*x**row['slope'],'--',color=color,label=f"{name}: slope={row['slope']:.3f}")
    # A slope -1 reference, anchored at observed rank one, not a fitted count.
    x=np.array([1,len(terms)])
    ax.loglog(x,float(terms.iloc[0]['cf'])/x,':',color='#65856A',label='Slope -1 reference (rank-one anchor)')
    ax.set(xlabel='Term rank',ylabel='Collection frequency',title='Yelp rank–frequency distribution')
    ax.grid(alpha=.2,which='both'); ax.legend(fontsize=8)
    for suffix in ('png','pdf'):
        fig.savefig(output/f'zipf_loglog.{suffix}',dpi=220)
    plt.close(fig)
    summary={'status':'COMPLETED','observed_types':len(terms),'total_tokens':int(terms['cf'].sum()),
             'hapax_types':int((terms['cf']==1).sum()),'punctuation_filter':['!','?','#'],
             'vocabulary_sha256':file_sha256(path),'vocabulary_metadata':metadata,'tokenizer':identity,
             'fits':fits,'method':'Descriptive OLS on log CF vs log rank; no formal goodness-of-fit test.'}
    write_json(output/'zipf_summary.json',summary)
    (output/'report_notes.md').write_text(
        '# Zipf results\n\n'+pd.DataFrame(fits).to_string(index=False)+
        '\n\nThe full curve is always shown. Compare global and core fits; 500/1000/5000-rank fits examine core-boundary sensitivity. Frequency >=5 is a separate sensitivity check, not a rule for choosing the most favorable fit. Report departures; no arbitrary pass/fail thresholds are applied.\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return summary


__all__ = ["analyze_zipf"]
