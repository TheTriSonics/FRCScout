import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { ScoutMatchComponent } from './components/scout-match/scout-match.component';
import { ScoutPitComponent } from './components/scout-pit/scout-pit.component';
import { PitViewComponent } from './components/pit-view/pit-view.component';
import { DisplayScheduleComponent } from './components/display-schedule/display-schedule.component';
import { SettingsComponent } from './components/settings/settings.component';

const routes: Routes = [
  /*
  {
    path: 'time-keeper',
    component: TimeKeeperComponent,
  },
  */
  {
    path: 'scout-match',
    component: ScoutMatchComponent,
  },
  {
    path: 'schedule',
    component: DisplayScheduleComponent,
  },
  {
    path: 'scout-pit',
    component: ScoutPitComponent,
  },
  {
    path: 'view-pits',
    component: PitViewComponent,
  },
  {
    path: 'settings',
    component: SettingsComponent,
  },
  /*
  {
    path: 'view-results',
    component: ScoutMatchViewComponent,
  },
  {
    path: 'team-details',
    component: TeamDetailsComponent,
  },
  {
    path: 'team-details/:teamKey',
    component: TeamDetailsComponent,
  },
  {
    path: '',
    component: SettingsComponent,
  },
  {
    path: 'helddata',
    component: HeldDataComponent,
  },
  */

];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
