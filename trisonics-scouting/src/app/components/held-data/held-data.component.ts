import { Component, OnInit } from '@angular/core';
import { AppDataService } from 'src/app/shared/services/app-data.service';
import { TimeDataService } from 'src/app/shared/services/time-data.service';
import { MatSnackBar } from '@angular/material/snack-bar';

@Component({
  selector: 'app-held-data',
  templateUrl: './held-data.component.html',
  styleUrls: ['./held-data.component.scss'],
})
export class HeldDataComponent implements OnInit {
  public sendingData = false;

  public uploadError = false;

  constructor(
    public appData: AppDataService,
    public timeData: TimeDataService,
    public snackbar: MatSnackBar,
  ) { }

  ngOnInit(): void {
  }

  public uploadData(): void {
    this.sendingData = true;
    this.appData.heldScoutData.forEach(async (sd) => {
      await this.appData.postResults(sd).toPromise().catch((err) => {
        console.error(err);
        this.uploadError = true;
        this.sendingData = false;
        this.snackbar.open(
          'Error uploading data, please try again.',
          'Close',
          { duration: 5000, panelClass: ['snackbar-error'] },
        );
      });
    });

    this.appData.heldPitData.forEach(async (sd) => {
      await this.appData.postPitResults(sd).toPromise().catch((err) => {
        console.error(err);
        this.uploadError = true;
        this.sendingData = false;
        this.snackbar.open(
          'Error uploading data, please try again.',
          'Close',
          { duration: 5000, panelClass: ['snackbar-error'] },
        );
      });
    });

    this.timeData.heldData.forEach(async (te) => {
      await this.timeData.postTimeEntry(te).toPromise().catch((err) => {
        console.error(err);
        this.uploadError = true;
        this.sendingData = false;
        this.snackbar.open(
          'Error uploading data, please try again.',
          'Close',
          { duration: 5000, panelClass: ['snackbar-error'] },
        );
      });
    });
    this.sendingData = false;
  }

  get hasScoutData(): boolean {
    return this.appData.heldScoutData.length > 0;
  }

  get hasPitData(): boolean {
    return this.appData.heldPitData.length > 0;
  }

  get hasTimeData(): boolean {
    return this.timeData.heldData.length > 0;
  }
}

export default HeldDataComponent;
