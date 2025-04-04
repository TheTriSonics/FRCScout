import { Component, OnInit } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { TBAEvent } from 'src/app/shared/models/tba-event.model';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { TBAMatch } from 'src/app/shared/models/tba-match.model';
import { AppDataService } from 'src/app/shared/services/app-data.service';
import { debounceTime } from 'rxjs/operators';

@Component({
  selector: 'app-settings',
  templateUrl: './settings.component.html',
  styleUrls: ['./settings.component.scss'],
})
export class SettingsComponent implements OnInit {
  public teamListLoading = false;

  public matchListFailure = false;

  public teamListFailure = false;

  public matchListLoading = false;

  public teamList: TBATeam[] = [];

  public matchList: TBAMatch[] = [];

  public fgSettings: FormGroup = new FormGroup({
    showConfetti: new FormControl(this.appData.showConfetti),
    teamKey: new FormControl(this.appData.teamKey),
    scouterName: new FormControl(this.appData.scouterName, Validators.required),
    eventKey: new FormControl(this.appData.eventKey, Validators.required),
  });

  constructor(
    public appData: AppDataService,
  ) { }

  ngOnInit(): void {
    this.teamReload();
    this.fgSettings.get('teamKey')?.valueChanges.subscribe((tk) => {
      this.appData.teamKey = tk;
      this.appData.secretKey = tk;
    });
    this.fgSettings.get('scouterName')?.valueChanges.subscribe((sn) => {
      this.appData.scouterName = sn;
    });
    this.fgSettings.get('eventKey')?.valueChanges.pipe(debounceTime(500)).subscribe((ek) => {
      this.appData.eventKey = ek;
      this.teamReload();
    });
  }

  public teamReload(force = false): void {
    const ek = this.appData.eventKey;
    this.teamListLoading = true;
    this.matchListFailure = false;
    this.teamListFailure = false;
    let params = {};
    if (force) {
      params = { force: true };
    }
    this.appData.getEventTeamList(ek, params).subscribe((tl) => {
      this.teamListLoading = false;
      this.teamList = tl;
    }, (err) => {
      console.log('error loading match list.')
      this.matchListFailure = true;
    });
    this.appData.getEventMatchList(ek, params).subscribe((ml) => {
      this.matchListLoading = false;
      this.matchList = ml;
      console.log(this.matchList);
    }, (err) => {
      console.log('error loading team list.')
      this.teamListFailure = true;
    });
  }

  public forceTeamReload(): void {
    this.teamReload(true);
  }

  get dataLoading(): boolean {
    return this.teamListLoading || this.matchListLoading;
  }

  get dualLoadingFailure(): boolean {
    return this.matchListFailure && this.teamListFailure;
  }

  get suggestedEventKey(): string {
    return '';
  }
}

export default SettingsComponent;
