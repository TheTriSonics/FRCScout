import { Component, OnInit } from '@angular/core';
import { PitResult } from 'src/app/shared/models/pit-result.model';
import AppDataService from 'src/app/shared/services/app-data.service';

@Component({
  selector: 'app-view-pits',
  templateUrl: './view-pits.component.html',
  styleUrls: ['./view-pits.component.scss'],
})
export class ViewPitsComponent implements OnInit {
  public pitResultList: PitResult[] = [];

  constructor(
    public appData: AppDataService,
  ) { }

  ngOnInit(): void {
    this.appData.getPitResults(this.appData.teamKey, this.appData.eventKey, null)
      .subscribe((pitResults) => {
        this.pitResultList = pitResults;
      });
  }
}

export default ViewPitsComponent;
