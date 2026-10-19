// Sample athlete for the tests: the PRs and the history that barra.html ships
// empty in the repo. Example numbers, frozen so the tests stay stable.
export const SEED_MAXES = {
  back_squat:72, front_squat:68, ohs:25, clean:35, power_clean:47, squat_clean:32.5,
  clean_jerk:47, snatch:33, power_snatch:30, squat_snatch:27.5,
  push_press:47, push_jerk:41, split_jerk:41,
};
export const HIST_MAXES = {
  back_squat: {kg:87.2, date:'2026-10-16', sessions:18, recent:[85,84.3,87.2]},
  clean_jerk: {kg:50.6, date:'2026-06-19', sessions:9, recent:[52.9,50,50.6]},
  front_squat: {kg:81.2, date:'2026-10-14', sessions:26, recent:[81.4,81.4,81.2]},
  power_snatch: {kg:40, date:'2026-10-14', sessions:6, recent:[35.7,38.7,40]},
  snatch: {kg:34.5, date:'2026-06-22', sessions:7, recent:[34.9,29.4,34.5]},
  squat_snatch: {kg:40.6, date:'2026-10-16', sessions:14, recent:[40,40,40.6]},
};
