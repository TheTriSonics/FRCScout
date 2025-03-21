import { Component, OnInit } from '@angular/core';
import { FormGroup, FormControl, Validators } from '@angular/forms';
import { AppDataService } from 'src/app/shared/services/app-data.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { PitResult } from 'src/app/shared/models/pit-result.model';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';

@Component({
  selector: 'app-scout-pit',
  templateUrl: './scout-pit.component.html',
  styleUrls: ['./scout-pit.component.scss'],
})
export class ScoutPitComponent implements OnInit {
  public teamList: TBATeam[] = [];

  public imageList: string[] = [];

  public pitResultList: PitResult[] = [];

  public matchResultsList: ScoutResult[] = [];

  public showExisting = false;

  public pitDataLoading = false;

  public pitDataSending = false;

  private allPitData: PitResult[] = [];

  public allPitDataLoaded = false;

  public matchesLoaded = false;

  public ratings: number[] = Array.from({ length: 21 }, (_, index) => index - 10);

  public fgScoutPit: FormGroup = new FormGroup({
    scouterName: new FormControl(this.appData.scouterName, Validators.required),
    teamKey: new FormControl(this.appData.teamKey, Validators.required),
    scoutingTeam: new FormControl(this.appData.scoutingData.scouting_team, [
      Validators.required,
      Validators.min(1),
    ]),
    eventKey: new FormControl(this.appData.eventKey, Validators.required),

    driveTrain: new FormControl(''),
    robotNotes: new FormControl(''),
  });

  constructor(
    public appData: AppDataService,
    public snackbar: MatSnackBar,
  ) { }

  ngOnInit(): void {
    this.loadData();
    console.log('ratings', this.ratings);
    this.fgScoutPit.get('eventKey')?.valueChanges.subscribe((eventKey) => {
      this.appData.eventKey = eventKey;
      this.loadData();
    });
    this.fgScoutPit.get('scoutingTeam')?.valueChanges.subscribe((teamKey) => {
      this.loadPitData(teamKey);
      this.appData.getRobotData(teamKey).subscribe((data) => {
        if (data) {
          this.matchResultsList.push(...data);
        }
        this.matchesLoaded = true;
      });
    });
  }

  private loadPitData(teamKey: string): void {
    this.showExisting = true;
    this.pitDataLoading = true;
    this.appData
      .getPitResults(this.appData.teamKey, this.appData.eventKey, teamKey)
      .subscribe((data) => {
        console.log('pit data', JSON.stringify(data, null, 4));
        this.pitResultList = data;
        this.pitDataLoading = false;
      });
  }

  public viewPitResult(pr: PitResult): void {
    console.log('clickly', pr);
  }

  private loadData(): void {
    this.allPitDataLoaded = false;
    this.appData.getEventTeamList(this.appData.eventKey).subscribe((tl) => {
      this.teamList = tl;
    });
    this.appData.getPitResults(this.appData.teamKey, this.appData.eventKey, null)
      .subscribe((pd) => {
        this.allPitData = pd;
        console.log('pit data:', pd);
        this.allPitDataLoaded = true;
      });
  }

  get pitData(): PitResult {
    const ret = {
      scouter_name: this.fgScoutPit.get('scouterName')?.value,
      secret_team_key: this.fgScoutPit.get('teamKey')?.value.toLowerCase().trim(),
      event_key: this.fgScoutPit.get('eventKey')?.value,
      scouting_team: this.fgScoutPit.get('scoutingTeam')?.value,
      drive_train: this.fgScoutPit.get('driveTrain')?.value,
      robot_notes: this.fgScoutPit.get('robotNotes')?.value,
      images: this.imageList,
    } as PitResult;
    return ret;
  }

  public resetForm(): void {
    this.fgScoutPit.get('scoutingTeam')?.setValue(0);
    this.fgScoutPit.get('robotNotes')?.setValue('');
    this.imageList = [];
  }

  public sendData(): void {
    if (this.fgScoutPit.valid) {
      this.pitDataSending = true;
      this.appData.postPitResults(this.pitData).subscribe({
        next: () => {
          this.snackbar.open(
            'Success! Data uploaded!',
            'Close',
            { duration: 5000, panelClass: ['snackbar-success'] },
          );
          this.pitDataSending = false;
          this.resetForm();
        },
        error: (err) => {
          this.pitDataSending = false;
          this.snackbar.open(
            'Error uploading data',
            'Close',
            { duration: 5000, panelClass: ['snackbar-error'] },
          );
        },
      });
    } else {
      const fields: string[] = [];
      if (!this.fgScoutPit.get('scouterName')?.valid) {
        fields.push('scouter name');
      }
      if (!this.fgScoutPit.get('scoutingTeam')?.valid) {
        fields.push('team you are scouting');
      }
      if (!this.fgScoutPit.get('eventKey')?.valid) {
        fields.push('event you are scouting');
      }
      const msg = `Please enter a value for ${fields.join(', ')}`;
      alert(msg);
    }
  }

  public uploadImage($event: any): void {
    console.log('uploading image');
    const fileReader = new FileReader();
    fileReader.onload = () => {
      this.resizeImage(fileReader.result).then((res) => {
        this.imageList.push(res as string);
      });
    };
    fileReader.readAsDataURL($event.target.files[0]);
  }

  public resizeImage(imageURL: any): Promise<any> {
    return new Promise((resolve) => {
      const maxImageWidth = 1024;
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement('canvas');
        const origWidth = image.width;
        let actualWidth = origWidth;
        let actualHeight = image.height;
        if (origWidth > maxImageWidth) {
          // Shrink the image
          actualWidth = maxImageWidth;
          const ratio = maxImageWidth / image.width;
          actualHeight = image.height * ratio;
        }
        canvas.width = actualWidth;
        canvas.height = actualHeight;
        const ctx = canvas.getContext('2d');
        if (ctx != null) {
          ctx.drawImage(image, 0, 0, actualWidth, actualHeight);
        }
        const data = canvas.toDataURL('image/jpeg', 1);
        resolve(data);
      };
      image.src = imageURL;
    });
  }

  public isScouted(teamNumber: number): string {
    console.log('finding', teamNumber);
    const found = this.pitResultList.find((t) => t.scouting_team === teamNumber);
    console.log('found', found);
    if (found) {
      return '';
    }
    return 'UNSCOUTED';
  }

  public getMatches(teamNumber: number): ScoutResult[] {
    return this.matchResultsList.filter((pr) => pr.scouting_team === teamNumber);
  }
}

export default ScoutPitComponent;
