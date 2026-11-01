# Zipf results

                 fit  rank_min  rank_max  types     slope   zipf_s            K  r_squared_log_space
           all_ranks         1    685120 685120 -1.792067 1.792067 1.454233e+10             0.961559
          rank_1_500         1       500    500 -0.967446 0.967446 8.252564e+07             0.995961
         rank_1_1000         1      1000   1000 -1.041164 1.041164 1.161308e+08             0.992781
         rank_1_5000         1      5000   5000 -1.280345 1.280345 4.630738e+08             0.987344
    rank_1000_100000      1000    100000  99001 -2.061047 2.061047 3.186307e+11             0.995678
frequency_at_least_5         1    173341 173341 -2.037602 2.037602 2.309630e+11             0.991095

The full curve is always shown. Compare global and core fits; 500/1000/5000-rank fits examine core-boundary sensitivity. Frequency >=5 is a separate sensitivity check, not a rule for choosing the most favorable fit. Report departures; no arbitrary pass/fail thresholds are applied.
