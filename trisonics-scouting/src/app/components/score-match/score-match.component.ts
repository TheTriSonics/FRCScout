import { Component, OnInit, AfterViewInit } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';

@Component({
  selector: 'app-score-match',
  templateUrl: './score-match.component.html',
  styleUrls: ['./score-match.component.scss'],
})
export class ScoreMatchComponent implements OnInit, AfterViewInit {
  public uploadError = false;

  public teamList: TBATeam[] = [];

  public sendingData = false;

  public fgMatch: FormGroup = new FormGroup({
    autoNothing: new FormControl(this.appData.autoNothing),
    autoEngaged: new FormControl(this.appData.autoEngaged),
    autoDocked: new FormControl(this.appData.autoDocked),
    autoCommunity: new FormControl(this.appData.autoCommunity),

    endNothing: new FormControl(this.appData.endgameNothing),
    endDead: new FormControl(this.appData.endgameDeadRobot),
    endParked: new FormControl(this.appData.endgameParked),
    endDocked: new FormControl(this.appData.endgameDocked),
    endEngaged: new FormControl(this.appData.endgameEngaged),
    scouterName: new FormControl(this.appData.scouterName, Validators.required),
    teamKey: new FormControl(this.appData.teamKey),
    scoutingTeam: new FormControl(this.appData.scoutingTeam, [
      Validators.required,
      Validators.min(1),
    ]),
    eventKey: new FormControl(this.appData.eventKey, Validators.required),
    match: new FormControl(this.appData.match, [
      Validators.required,
      Validators.pattern('^[1-9][0-9]*$'), // Fun with regex to force only numbers as valid input
    ]),
    matchNotes: new FormControl(this.appData.matchNotes),
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
      this.teamList = tl;
    });
  }

  public ngAfterViewInit(): void {
    // Create event handlers for text input form controls
    // The ? operator here is used to abort the command if the get() returns
    // a null or undefined value.
    // We're also creating a subscription that processes the tiny little function
    // that we define within the subscribe() method itself.
    this.fgMatch.get('scouterName')?.valueChanges.subscribe((x) => {
      this.appData.scouterName = x;
    });
    this.fgMatch.get('teamKey')?.valueChanges.subscribe((x) => {
      this.appData.teamKey = x;
    });
    this.fgMatch.get('eventKey')?.valueChanges.subscribe((x) => {
      this.appData.eventKey = x;
      this.loadData();
    });
    this.fgMatch.get('match')?.valueChanges.subscribe((x) => {
      this.appData.match = x;
    });
    this.fgMatch.get('scoutingTeam')?.valueChanges.subscribe((x) => {
      // We use the + operator to force the value to be a number.
      this.appData.scoutingTeam = +x;
    });
    // Now let's define one with a defined function instead of an anonymous one.
    this.fgMatch.get('matchNotes')?.valueChanges.subscribe((x) => this.updateMatchNotes(x));

    this.fgMatch.get('eventKey')?.valueChanges.subscribe((eventKey) => {
      this.appData.eventKey = eventKey;
      this.loadData();
    });

    this.fgMatch.get('autoNothing')?.valueChanges.subscribe((val) => {
      this.appData.autoNothing = val;
      if (val) {
        this.fgMatch.get('autoCommunity')?.setValue(false);
      }
    });

    this.fgMatch.get('autoCommunity')?.valueChanges.subscribe((val) => {
      this.appData.autoCommunity = val;
      if (val) {
        this.fgMatch.get('autoNothing')?.setValue(false);
      }
    });

    this.fgMatch.get('autoDocked')?.valueChanges.subscribe((val) => {
      this.appData.autoDocked = val;
      if (val) {
        this.fgMatch.get('autoEngaged')?.setValue(false);
      }
    });
    this.fgMatch.get('autoEngaged')?.valueChanges.subscribe((val) => {
      this.appData.autoEngaged = val;
      if (val) {
        this.fgMatch.get('autoDocked')?.setValue(false);
      }
    });

    this.fgMatch.get('endNothing')?.valueChanges.subscribe((val) => {
      this.appData.endgameNothing = val;
      if (val) {
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endParked')?.setValue(false);
        this.fgMatch.get('endDocked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endDead')?.valueChanges.subscribe((val) => {
      this.appData.endgameDeadRobot = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endParked')?.setValue(false);
        this.fgMatch.get('endDocked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endParked')?.valueChanges.subscribe((val) => {
      this.appData.endgameParked = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endDocked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endDocked')?.valueChanges.subscribe((val) => {
      this.appData.endgameDocked = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endParked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endParked')?.valueChanges.subscribe((val) => {
      this.appData.endgameParked = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endDocked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endDocked')?.valueChanges.subscribe((val) => {
      this.appData.endgameDocked = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endParked')?.setValue(false);
        this.fgMatch.get('endEngaged')?.setValue(false);
      }
    });

    this.fgMatch.get('endEngaged')?.valueChanges.subscribe((val) => {
      this.appData.endgameEngaged = val;
      if (val) {
        this.fgMatch.get('endNothing')?.setValue(false);
        this.fgMatch.get('endDead')?.setValue(false);
        this.fgMatch.get('endParked')?.setValue(false);
        this.fgMatch.get('endDocked')?.setValue(false);
      }
    });
  }

  public updateMatchNotes(notes: string): void {
    this.appData.matchNotes = notes;
  }

  public autoCubeHighInc(): void {
    this.appData.autoCubeHigh += 1;
  }

  public autoCubeHighDec(): void {
    if (this.appData.autoCubeHigh > 0) {
      this.appData.autoCubeHigh -= 1;
    }
  }

  public autoCubeMediumInc(): void {
    this.appData.autoCubeMedium += 1;
  }

  public autoCubeMediumDec(): void {
    if (this.appData.autoCubeMedium > 0) {
      this.appData.autoCubeMedium -= 1;
    }
  }

  public autoCubeLowInc(): void {
    this.appData.autoCubeLow += 1;
  }

  public autoCubeLowDec(): void {
    if (this.appData.autoCubeLow > 0) {
      this.appData.autoCubeLow -= 1;
    }
  }

  public autoConeHighInc(): void {
    this.appData.autoConeHigh += 1;
  }

  public autoConeHighDec(): void {
    if (this.appData.autoConeHigh > 0) {
      this.appData.autoConeHigh -= 1;
    }
  }

  public autoConeMediumInc(): void {
    this.appData.autoConeMedium += 1;
  }

  public autoConeMediumDec(): void {
    if (this.appData.autoConeMedium > 0) {
      this.appData.autoConeMedium -= 1;
    }
  }

  public autoConeLowInc(): void {
    this.appData.autoConeLow += 1;
  }

  public autoConeLowDec(): void {
    if (this.appData.autoConeLow > 0) {
      this.appData.autoConeLow -= 1;
    }
  }

  public teleopCubeHighInc(): void {
    this.appData.teleopCubeHigh += 1;
  }

  public teleopCubeHighDec(): void {
    if (this.appData.teleopCubeHigh > 0) {
      this.appData.teleopCubeHigh -= 1;
    }
  }

  public teleopCubeMediumInc(): void {
    this.appData.teleopCubeMedium += 1;
  }

  public teleopCubeMediumDec(): void {
    if (this.appData.teleopCubeMedium > 0) {
      this.appData.teleopCubeMedium -= 1;
    }
  }

  public teleopCubeLowInc(): void {
    this.appData.teleopCubeLow += 1;
  }

  public teleopCubeLowDec(): void {
    if (this.appData.teleopCubeLow > 0) {
      this.appData.teleopCubeLow -= 1;
    }
  }

  public teleopConeHighInc(): void {
    this.appData.teleopConeHigh += 1;
  }

  public teleopConeHighDec(): void {
    if (this.appData.teleopConeHigh > 0) {
      this.appData.teleopConeHigh -= 1;
    }
  }

  public teleopConeMediumInc(): void {
    this.appData.teleopConeMedium += 1;
  }

  public teleopConeMediumDec(): void {
    if (this.appData.teleopConeMedium > 0) {
      this.appData.teleopConeMedium -= 1;
    }
  }

  public teleopConeLowInc(): void {
    this.appData.teleopConeLow += 1;
  }

  public teleopConeLowDec(): void {
    if (this.appData.teleopConeLow > 0) {
      this.appData.teleopConeLow -= 1;
    }
  }

  public endgameBuddyInc(): void {
    this.appData.buddyBots += 1;
  }

  public endgameBuddyDec(): void {
    if (this.appData.buddyBots > 0) {
      this.appData.buddyBots -= 1;
    }
  }

  get matchData(): ScoutResult {
    const ret = {
      scouter_name: this.appData.scouterName,
      secret_team_key: this.appData.teamKey.toLowerCase().trim(),
      event_key: this.appData.eventKey,
      match_key: this.appData.match,
      scouting_team: this.appData.scoutingTeam,

      auto_nothing: this.appData.autoNothing,
      auto_engaged: this.appData.autoEngaged,
      auto_docked: this.appData.autoDocked,
      auto_community: this.appData.autoCommunity,

      endgame_nothing: this.appData.endgameNothing,
      endgame_dead_robot: this.appData.endgameDeadRobot,
      endgame_engaged: this.appData.endgameEngaged,
      endgame_docked: this.appData.endgameDocked,
      endgame_parked: this.appData.endgameParked,

      auto_cubes_high: this.appData.autoCubeHigh,
      auto_cubes_medium: this.appData.autoCubeMedium,
      auto_cubes_low: this.appData.autoCubeLow,
      auto_cones_high: this.appData.autoConeHigh,
      auto_cones_medium: this.appData.autoConeMedium,
      auto_cones_low: this.appData.autoConeLow,
      teleop_cubes_high: this.appData.teleopCubeHigh,
      teleop_cubes_medium: this.appData.teleopCubeMedium,
      teleop_cubes_low: this.appData.teleopCubeLow,
      teleop_cones_high: this.appData.teleopConeHigh,
      teleop_cones_medium: this.appData.teleopConeMedium,
      teleop_cones_low: this.appData.teleopConeLow,

      match_notes: this.appData.matchNotes,
    } as ScoutResult;
    return ret;
  }

  public uploadData(): void {
    if (this.fgMatch.valid) {
      this.sendingData = true;
      this.appData.postResults(this.matchData).subscribe({
        next: (data) => {
          this.uploadError = false;
          this.sendingData = false;
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
          this.snackbar.open(
            'Error uploading data, please try again.',
            'Close',
            { duration: 5000, panelClass: ['snackbar-error'] },
          );
        },
      });
    } else {
      const fields: string[] = [];
      if (!this.fgMatch.get('scouterName')?.valid) {
        fields.push('scouter name');
      }
      if (!this.fgMatch.get('scoutingTeam')?.valid) {
        fields.push('team you are scouting');
      }
      if (!this.fgMatch.get('eventKey')?.valid) {
        fields.push('event you are scouting');
      }
      if (!this.fgMatch.get('match')?.valid) {
        fields.push('match number');
      }

      const msg = 'Please enter a value for ' + fields.join(', ');
      alert(msg);
    }
  }

  public resetForm(): void {
    this.appData.autoConeHigh = 0;
    this.appData.autoConeMedium = 0;
    this.appData.autoConeLow = 0;
    this.appData.autoCubeHigh = 0;
    this.appData.autoCubeMedium = 0;
    this.appData.autoCubeLow = 0;
    this.appData.teleopConeHigh = 0;
    this.appData.teleopConeMedium = 0;
    this.appData.teleopConeLow = 0;
    this.appData.teleopCubeHigh = 0;
    this.appData.teleopCubeMedium = 0;
    this.appData.teleopCubeLow = 0;
    this.appData.buddyBots = 0;
    const bools = ['autoNothing', 'autoCommunity', 'autoEngaged', 'autoDocked',
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
    return JSON.stringify(this.matchData);
  }

  get gameJSONFormatted(): string {
    return JSON.stringify(this.matchData, null, 4);
  }
}

export default ScoreMatchComponent;
