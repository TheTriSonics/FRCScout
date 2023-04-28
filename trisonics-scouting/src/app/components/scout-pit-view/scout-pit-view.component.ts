import { Component, OnInit } from '@angular/core';
import { PitResult } from 'src/app/shared/models/pit-result.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import * as _ from 'lodash';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';

@Component({
  selector: 'app-scout-pit-view',
  templateUrl: './scout-pit-view.component.html',
  styleUrls: ['./scout-pit-view.component.scss'],
})
export class ScoutPitViewComponent implements OnInit {
  public teamList: TBATeam[] = [];

  public pitResultList: PitResult[] = [];

  public teamsLoaded = false;

  public resultsLoaded = false;

  constructor(
    public appData: AppDataService,
  ) { }

  ngOnInit(): void {
    this.appData.getEventTeamList(this.appData.eventKey).subscribe((teams) => {
      this.teamList = _.sortBy(teams, 'number');
      this.teamsLoaded = true;
    });
    this.appData.getPitResults(this.appData.teamKey, this.appData.eventKey, null)
      .subscribe((pitResults) => {
        this.pitResultList = _.sortBy(pitResults, 'scouting_team');
        this.resultsLoaded = true;
      });
  }

  public getPits(teamNumber: number): PitResult[] {
    return this.pitResultList.filter((pr) => pr.scouting_team === teamNumber);
  }
}

export default ScoutPitViewComponent;
