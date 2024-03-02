import { Component, OnInit, AfterViewInit } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { TBAAlliance, TBAMatch } from 'src/app/shared/models/tba-match.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';
import * as _ from 'lodash';
import ConfettiService from 'src/app/shared/services/confetti.service';

@Component({
  selector: 'app-scout-match',
  templateUrl: './scout-match.component.html',
  styleUrls: ['./scout-match.component.scss'],
})
export class ScoutMatchComponent implements OnInit, AfterViewInit {
  public uploadError = false;

  public fullTeamList: TBATeam[] = [];

  public matchList: TBAMatch[] = [];

  public matchNumber: number = 0;

  public blueBots: TBATeam[] = [];

  public redBots: TBATeam[] = [];

  public sendingData = false;

  public scoutingActive = false;

  public loadingTeams = true;

  public loadingMatches = true;

  public fgMatch: FormGroup = new FormGroup({
    scoutingTeam: new FormControl(1, [
      Validators.required,
    ]),
    match: new FormControl(1, [
      Validators.required,
    ]),
  });

  constructor(
    public appData: AppDataService,
    public snackbar: MatSnackBar,
    public confetti: ConfettiService,
  ) {}

  public ngOnInit(): void {
    this.matchNumber = 1;
    this.loadData();
  }

  private loadData(): void {
    console.log('this.app eventkey', this.appData.eventKey);
    this.appData.getEventTeamList(this.appData.eventKey).subscribe((tl) => {
      console.log('team list', tl);
      this.fullTeamList = tl;
      this.loadingTeams = false;
    });
    this.appData.getEventMatchList(this.appData.eventKey).subscribe((ml) => {
      console.log('match list', ml);
      let qm = ml.filter((m) => m.comp_level === 'qm');
      this.matchList = _.sortBy(qm, (m) => +m.match_number);
      this.loadingMatches = false;
    });
  }

  get loadingData(): boolean {
    return this.loadingTeams && this.loadingMatches;
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

  public launchConfetti(): void {
    this.confetti.canon(45, 0.1);
    this.confetti.canon(135, 0.9);
  }


  public autoAmpInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.auto_amp) {
      this.appData.scoutingData.auto_amp = 0;
    }
    this.appData.scoutingData.auto_amp += 1;
  }

  public autoAmpDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.auto_amp > 0) {
      this.appData.scoutingData.auto_amp -= 1;
    }
  }

  public autoSpeakerInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.auto_speaker) {
      this.appData.scoutingData.auto_speaker = 0;
    }
    this.appData.scoutingData.auto_speaker += 1;
  }

  public autoSpeakerDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.auto_speaker > 0) {
      this.appData.scoutingData.auto_speaker -= 1;
    }
  }

  public teleopAmpInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.teleop_amp) {
      this.appData.scoutingData.teleop_amp = 0;
    }
    this.appData.scoutingData.teleop_amp += 1;
  }

  public teleopAmpDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.teleop_amp > 0) {
      this.appData.scoutingData.teleop_amp -= 1;
    }
  }

  public teleopSpeakerInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.teleop_speaker) {
      this.appData.scoutingData.teleop_speaker = 0;
    }
    this.appData.scoutingData.teleop_speaker += 1;
  }

  public teleopSpeakerDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.teleop_speaker > 0) {
      this.appData.scoutingData.teleop_speaker -= 1;
    }
  }

  public endgameTrapInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.endgame_trap) {
      this.appData.scoutingData.endgame_trap = 0;
    }
    this.appData.scoutingData.endgame_trap += 1;
  }

  public endgameTrapDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.endgame_trap > 0) {
      this.appData.scoutingData.endgame_trap -= 1;
    }
  }

  public endgameMicrophoneInc(): void {
    this.launchConfetti();
    if (!this.appData.scoutingData.endgame_microphone) {
      this.appData.scoutingData.endgame_microphone = 0;
    }
    this.appData.scoutingData.endgame_microphone += 1;
  }

  public endgameMicrophoneDec(): void {
    this.launchConfetti();
    if (this.appData.scoutingData.endgame_microphone > 0) {
      this.appData.scoutingData.endgame_microphone -= 1;
    }
  }

  get scoutingTeamSelected(): boolean {
    const val = this.fgMatch.get('scoutingTeam')?.value;
    console.log('scouting team value', val);
    return val > 1;
  }

  public uploadData(): void {
    if (this.fgMatch.valid) {
      this.appData.scoutingData.scouter_name = this.appData.scouterName;
      this.appData.scoutingData.secret_team_key = this.appData.secretKey;
      this.appData.scoutingData.event_key = this.appData.eventKey;
      this.appData.scoutingData.scouting_team = this.fgMatch.get('scoutingTeam')?.value;
      this.appData.scoutingData.match_key = this.fgMatch.get('match')?.value;
      this.sendingData = true;
      this.appData.postResults(this.appData.scoutingData).subscribe({
        next: (data: any) => {
          this.uploadError = false;
          this.sendingData = false;
          this.scoutingActive = false;
          this.matchNumber = 1;
          // this.confetti.canon();
          this.snackbar.open(
            'Success! Data uploaded!',
            'Close',
            { duration: 5000, panelClass: ['snackbar-success'] },
          );
          // Reset form controls that should be reset between matches
          this.resetForm();
        },
        error: (err: any) => {
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
    this.appData.scoutingData.auto_zone = false;
    this.appData.scoutingData.auto_nothing = false;
    this.appData.scoutingData.auto_amp = 0;
    this.appData.scoutingData.auto_speaker = 0;
    this.appData.scoutingData.teleop_amp = 0;
    this.appData.scoutingData.teleop_speaker = 0;
    this.appData.scoutingData.endgame_trap = 0;
    this.appData.scoutingData.endgame_microphone = 0;
    this.appData.scoutingData.endgame_harmony = false;
    this.appData.scoutingData.endgame_onstage = false;
    this.appData.scoutingData.endgame_park = false;
    this.appData.scoutingData.match_notes = '';
  }

  public resetFormConfirm(): void {
    const resp = confirm('Are you sure you want to clear the form?');
    if (resp) {
      this.resetForm();
    }
  }

  // TODO: Tie into match number like I wanted to
  get teamList(): TBATeam[] {
    if (true) {
      const teamList: TBATeam[] = [];
      this.blueBots = [] as TBATeam[]
      this.redBots = [] as TBATeam[]
      const match = this.matchList.find((m) => m.match_number == this.matchNumber) as TBAMatch;
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
      // console.log('returning', teamList);
      return teamList
    }
    return [] as TBATeam[];
  }

  public getMatchLabel(m: TBAMatch): string {
    return `${m.match_number}`;
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
