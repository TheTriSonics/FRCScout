import { Component, OnInit, Input } from '@angular/core';
import { PitResult } from 'src/app/shared/models/pit-result.model';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';

@Component({
  selector: 'app-scout-pit-view',
  templateUrl: './scout-pit-view.component.html',
  styleUrls: ['./scout-pit-view.component.scss'],
})
export class ScoutPitViewComponent implements OnInit {
  @Input() public pitResult!: PitResult;

  @Input() public matches = false;

  public matchesLoaded = false;

  public matchResults: ScoutResult[] = [];

  public nickname = '...loading..';

  constructor(
    private appData: AppDataService,
  ) { }

  public ngOnInit(): void {
    this.appData.getEventTeamList(this.pitResult.event_key).subscribe((teams) => {
      const team = teams.find((t) => t.number === this.pitResult.scouting_team);
      if (team) {
        this.nickname = team.name;
      } else {
        console.error('no team found for ', this.pitResult.scouting_team);
      }
    });
    if (this.matches) {
      this.appData.getRobotData(this.pitResult.scouting_team).subscribe((robotData) => {
        this.matchResults = robotData.filter((rd) => rd.match_notes.length > 1);
        this.matchResults.forEach((mr) => {
          console.log('match result: ', mr.match_notes);
        });
        this.matchesLoaded = true;
      });
    }
  }

  get wheelType(): string {
    const pr = this.pitResult;
    let retVal = 'unknown';
    if (pr.wheel_inflated) {
      retVal = 'inflated';
    } else if (pr.wheel_solid) {
      retVal = 'solid';
    } else if (pr.wheel_omni) {
      retVal = 'omni';
    } else if (pr.wheel_mec) {
      retVal = 'mecanum';
    }

    return retVal;
  }

  get teamDisplayName(): string {
    return `${this.pitResult.scouting_team} (${this.nickname})`;
  }
}

export default ScoutPitViewComponent;
