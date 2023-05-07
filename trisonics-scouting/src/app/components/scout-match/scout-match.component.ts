import { Component, OnInit, AfterViewInit } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { TBAAlliance, TBAMatch } from 'src/app/shared/models/tba-match.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';

@Component({
  selector: 'app-scout-match',
  templateUrl: './scout-match.component.html',
  styleUrls: ['./scout-match.component.scss'],
})
export class ScoutMatchComponent implements OnInit, AfterViewInit {
  public uploadError = false;

  public fullTeamList: TBATeam[] = [];

  public matchList: TBAMatch[] = [];

  public matchNumber: number | undefined = undefined;

  public blueBots: TBATeam[] = [];

  public redBots: TBATeam[] = [];

  public sendingData = false;

  public scoutingActive = false;

  public fgMatch: FormGroup = new FormGroup({
    scoutingTeam: new FormControl(this.appData.scoutingData.scouting_team, [
      Validators.required,
      Validators.min(1),
    ]),
    match: new FormControl(this.appData.scoutingData.match_key, [
      Validators.required,
      Validators.pattern('^[1-9][0-9]*$'), // Fun with regex to force only numbers as valid input
    ]),
  });

  constructor(
    public appData: AppDataService,
    public snackbar: MatSnackBar,
  ) {}

  public ngOnInit(): void {
    this.loadData();
  }

  private loadData(): void {
    console.log('this.app eventkey', this.appData.eventKey);
    this.appData.getEventTeamList(this.appData.eventKey).subscribe((tl) => {
      console.log('team list', tl);
      this.fullTeamList = tl;
    });
    this.appData.getEventMatchList(this.appData.eventKey).subscribe((ml) => {
      console.log('match list', ml);
      this.matchList = ml;
    });
  }

  public ngAfterViewInit(): void {
    this.fgMatch.get('match')?.valueChanges.subscribe((x) => {
      this.matchNumber = +x;
      console.log('match changed', x);
    });
  }

  public beginScouting(): void {
    this.scoutingActive = true;
  }

  public autoCubeHighInc(): void {
    this.appData.scoutingData.auto_cubes_high += 1;
  }

  public autoCubeHighDec(): void {
    if (this.appData.scoutingData.auto_cubes_high > 0) {
      this.appData.scoutingData.auto_cubes_high -= 1;
    }
  }

  public autoCubeMediumInc(): void {
    this.appData.scoutingData.auto_cubes_medium += 1;
  }

  public autoCubeMediumDec(): void {
    if (this.appData.scoutingData.auto_cubes_medium > 0) {
      this.appData.scoutingData.auto_cubes_medium -= 1;
    }
  }

  public autoCubeLowInc(): void {
    this.appData.scoutingData.auto_cubes_low += 1;
  }

  public autoCubeLowDec(): void {
    if (this.appData.scoutingData.auto_cubes_low > 0) {
      this.appData.scoutingData.auto_cubes_low -= 1;
    }
  }

  public autoConeHighInc(): void {
    this.appData.scoutingData.auto_cones_high += 1;
  }

  public autoConeHighDec(): void {
    if (this.appData.scoutingData.auto_cones_high > 0) {
      this.appData.scoutingData.auto_cones_high -= 1;
    }
  }

  public autoConeMediumInc(): void {
    this.appData.scoutingData.auto_cones_medium += 1;
  }

  public autoConeMediumDec(): void {
    if (this.appData.scoutingData.auto_cones_medium > 0) {
      this.appData.scoutingData.auto_cones_medium -= 1;
    }
  }

  public autoConeLowInc(): void {
    this.appData.scoutingData.auto_cones_low += 1;
  }

  public autoConeLowDec(): void {
    if (this.appData.scoutingData.auto_cones_low > 0) {
      this.appData.scoutingData.auto_cones_low -= 1;
    }
  }

  public teleopCubeHighInc(): void {
    this.appData.scoutingData.teleop_cubes_high += 1;
  }

  public teleopCubeHighDec(): void {
    if (this.appData.scoutingData.teleop_cubes_high > 0) {
      this.appData.scoutingData.teleop_cubes_high -= 1;
    }
  }

  public teleopCubeMediumInc(): void {
    this.appData.scoutingData.teleop_cubes_medium += 1;
  }

  public teleopCubeMediumDec(): void {
    if (this.appData.scoutingData.teleop_cubes_medium > 0) {
      this.appData.scoutingData.teleop_cubes_medium -= 1;
    }
  }

  public teleopCubeLowInc(): void {
    this.appData.scoutingData.teleop_cubes_low += 1;
  }

  public teleopCubeLowDec(): void {
    if (this.appData.scoutingData.teleop_cubes_low > 0) {
      this.appData.scoutingData.teleop_cubes_low -= 1;
    }
  }

  public teleopConeHighInc(): void {
    this.appData.scoutingData.teleop_cones_high += 1;
  }

  public teleopConeHighDec(): void {
    if (this.appData.scoutingData.teleop_cones_high > 0) {
      this.appData.scoutingData.teleop_cones_high -= 1;
    }
  }

  public teleopConeMediumInc(): void {
    this.appData.scoutingData.teleop_cones_medium += 1;
  }

  public teleopConeMediumDec(): void {
    if (this.appData.scoutingData.teleop_cones_medium > 0) {
      this.appData.scoutingData.teleop_cones_medium -= 1;
    }
  }

  public teleopConeLowInc(): void {
    this.appData.scoutingData.teleop_cones_low += 1;
  }

  public teleopConeLowDec(): void {
    if (this.appData.scoutingData.teleop_cones_low > 0) {
      this.appData.scoutingData.teleop_cones_low -= 1;
    }
  }

  public uploadData(): void {
    if (this.fgMatch.valid) {
      this.sendingData = true;
      this.appData.postResults(this.appData.scoutingData).subscribe({
        next: (data) => {
          this.uploadError = false;
          this.sendingData = false;
          this.scoutingActive = false;
          this.snackbar.open(
            'Success! Data uploaded!',
            'Close',
            { duration: 5000, panelClass: ['snackbar-success'] },
          );
          // Reset form controls that should be reset between matches
          this.resetForm();
        },
        error: (err) => {
          console.log('Error uploading data: ', err);
          this.uploadError = true;
          this.sendingData = false;
          this.scoutingActive = false;
          this.snackbar.open(
            'Error uploading data, please try again.',
            'Close',
            { duration: 5000, panelClass: ['snackbar-error'] },
          );
        },
      });
    } else {
      const fields: string[] = [];
      if (!this.fgMatch.get('scoutingTeam')?.valid) {
        fields.push('team you are scouting');
      }
      if (!this.fgMatch.get('match')?.valid) {
        fields.push('match number');
      }

      const msg = 'Please enter a value for ' + fields.join(', ');
      alert(msg);
    }
  }

  public resetForm(): void {
    this.appData.scoutingData.auto_cones_high = 0;
    this.appData.scoutingData.auto_cones_medium = 0;
    this.appData.scoutingData.auto_cones_low = 0;
    this.appData.scoutingData.auto_cubes_high = 0;
    this.appData.scoutingData.auto_cubes_medium = 0;
    this.appData.scoutingData.auto_cubes_low = 0;
    this.appData.scoutingData.teleop_cones_high = 0;
    this.appData.scoutingData.teleop_cones_medium = 0;
    this.appData.scoutingData.teleop_cones_low = 0;
    this.appData.scoutingData.teleop_cubes_high = 0;
    this.appData.scoutingData.teleop_cubes_medium = 0;
    this.appData.scoutingData.teleop_cubes_low = 0;
    const bools = ['autoNothing', 'autoCommunity', 'autoEngaged', 'autoDocked',
      'teleopHPDouble', 'teleopHPSingle',
      'endNothing', 'endDead', 'endEngaged', 'endDocked', 'endParked'];
    bools.forEach((b) => {
      this.fgMatch.get(b)?.setValue(false);
    });
    const strs = ['scoutingTeam', 'match', 'matchNotes'];
    strs.forEach((s) => {
      this.fgMatch.get(s)?.setValue('');
    });
  }

  public resetFormConfirm(): void {
    const resp = confirm('Are you sure you want to clear the form?');
    if (resp) {
      this.resetForm();
    }
  }

  get gameJSON(): string {
    return JSON.stringify(this.appData.scoutingData);
  }

  get gameJSONFormatted(): string {
    return JSON.stringify(this.appData.scoutingData, null, 4);
  }

  get teamList(): TBATeam[] {
    if (this.matchNumber) {
      const teamList: TBATeam[] = [];
      const match = this.matchList.find((m) => m.match_number === this.matchNumber) as TBAMatch;
      match?.alliances.blue.team_keys.forEach((t) => {
        const team = this.fullTeamList.find((ft) => `frc${ft.number}` === t) as TBATeam;
        this.blueBots.push(team);
        teamList.push(team);
      });
      match?.alliances.red.team_keys.forEach((t) => {
        const team = this.fullTeamList.find((ft) => `frc${ft.number}` === t) as TBATeam;
        this.redBots.push(team);
        teamList.push(team);
      });
      return teamList;
    }
    return [] as TBATeam[];
  }

  public getTeamLabel(t: TBATeam): string {
    let color = '';
    let position = 0;
    if (this.blueBots.includes(t)) {
      // Blue bot
      color = 'Blue';
      position = this.blueBots.indexOf(t) + 1;
    } else {
      // Red bot
      color = 'Red';
      position = this.redBots.indexOf(t) + 1;
    }
    return `${color} ${position}: ${t.number} - ${t.name} `;
  }
}

export default ScoutMatchComponent;
